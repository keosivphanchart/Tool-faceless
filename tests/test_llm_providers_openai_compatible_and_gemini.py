"""OpenAI, Groq, and Gemini as SCRIPT_PROVIDER options.

OpenAI and Groq share one HTTP call (_call_openai_compatible) since Groq's
hosted API deliberately mirrors OpenAI's /chat/completions shape — only the
base_url/key differ. Gemini has its own request/response shape entirely.

All three providers have a configurable base_url in Settings (unlike a
fixed SDK endpoint), so — same trick used for Ollama — these tests point
each provider at a real local HTTP server that replies with the shape that
provider's real API actually returns, and drive it through the public
generate_script() call. This proves the request payload and response
parsing against a real socket round-trip, not a mock.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from faceless_pipeline.config import settings
from faceless_pipeline.modules.scripts.generator import STORYBOARD_BEATS, generate_script

FAKE_SCRIPT_JSON = json.dumps(
    {
        "hook": "h",
        "promise": "p",
        "body": "body text here",
        "payoff": "pa",
        "cta": "c",
        "storyboard": [
            {"beat": beat, "visual": f"visual for {beat}", "keywords": [beat, "test"]}
            for beat in STORYBOARD_BEATS
        ],
    }
)


class _OpenAICompatibleHandler(BaseHTTPRequestHandler):
    received_requests: list[dict] = []
    response_content = FAKE_SCRIPT_JSON
    status_code = 200

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        type(self).received_requests.append(
            {"path": self.path, "body": body, "authorization": self.headers.get("Authorization")}
        )

        self.send_response(type(self).status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {"choices": [{"message": {"content": type(self).response_content}}]}
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):
        pass


class _GeminiHandler(BaseHTTPRequestHandler):
    received_requests: list[dict] = []
    response_content = FAKE_SCRIPT_JSON

    def do_POST(self):
        from urllib.parse import parse_qs, urlparse

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        type(self).received_requests.append({"path": parsed.path, "query": query, "body": body})

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {"candidates": [{"content": {"parts": [{"text": type(self).response_content}]}}]}
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):
        pass


def _start_server(handler_cls):
    handler_cls.received_requests = []
    handler_cls.response_content = FAKE_SCRIPT_JSON
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.fixture
def openai_server():
    server, thread = _start_server(_OpenAICompatibleHandler)
    _OpenAICompatibleHandler.status_code = 200

    original_provider, original_base, original_key = settings.script_provider, settings.openai_base_url, settings.openai_api_key
    settings.script_provider = "openai"
    settings.openai_base_url = f"http://127.0.0.1:{server.server_port}/v1"
    settings.openai_api_key = "sk-test-key"

    try:
        yield _OpenAICompatibleHandler
    finally:
        server.shutdown()
        thread.join()
        settings.script_provider, settings.openai_base_url, settings.openai_api_key = (
            original_provider, original_base, original_key,
        )


@pytest.fixture
def groq_server():
    server, thread = _start_server(_OpenAICompatibleHandler)
    _OpenAICompatibleHandler.status_code = 200

    original_provider, original_base, original_key = settings.script_provider, settings.groq_base_url, settings.groq_api_key
    settings.script_provider = "groq"
    settings.groq_base_url = f"http://127.0.0.1:{server.server_port}/openai/v1"
    settings.groq_api_key = "gsk-test-key"

    try:
        yield _OpenAICompatibleHandler
    finally:
        server.shutdown()
        thread.join()
        settings.script_provider, settings.groq_base_url, settings.groq_api_key = (
            original_provider, original_base, original_key,
        )


@pytest.fixture
def gemini_server():
    server, thread = _start_server(_GeminiHandler)

    original_provider, original_base, original_key, original_model = (
        settings.script_provider, settings.gemini_base_url, settings.gemini_api_key, settings.gemini_model,
    )
    settings.script_provider = "gemini"
    settings.gemini_base_url = f"http://127.0.0.1:{server.server_port}"
    settings.gemini_api_key = "gm-test-key"
    settings.gemini_model = "gemini-2.0-flash"

    try:
        yield _GeminiHandler
    finally:
        server.shutdown()
        thread.join()
        settings.script_provider, settings.gemini_base_url, settings.gemini_api_key, settings.gemini_model = (
            original_provider, original_base, original_key, original_model,
        )


def test_openai_hits_chat_completions_with_bearer_auth(db_session, openai_server):
    script = generate_script(db_session, topic="OpenAI provider test topic")

    assert len(openai_server.received_requests) == 1
    req = openai_server.received_requests[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["authorization"] == "Bearer sk-test-key"
    assert req["body"]["model"] == settings.openai_model
    assert req["body"]["response_format"] == {"type": "json_object"}
    roles = [m["role"] for m in req["body"]["messages"]]
    assert roles == ["system", "user"]
    assert script.script["hook"] == "h"
    assert len(script.script["storyboard"]) == 5


def test_groq_uses_same_openai_shaped_request(db_session, groq_server):
    script = generate_script(db_session, topic="Groq provider test topic")

    assert len(groq_server.received_requests) == 1
    req = groq_server.received_requests[0]
    assert req["path"] == "/openai/v1/chat/completions"
    assert req["authorization"] == "Bearer gsk-test-key"
    assert req["body"]["model"] == settings.groq_model
    assert script.script["hook"] == "h"


def test_openai_http_error_gives_actionable_message(db_session, openai_server):
    openai_server.status_code = 401

    with pytest.raises(RuntimeError, match="OpenAI API error"):
        generate_script(db_session, topic="OpenAI 401 test topic")


def test_gemini_hits_generatecontent_with_key_param_and_system_instruction(db_session, gemini_server):
    script = generate_script(db_session, topic="Gemini provider test topic")

    assert len(gemini_server.received_requests) == 1
    req = gemini_server.received_requests[0]
    assert req["path"] == "/models/gemini-2.0-flash:generateContent"
    assert req["query"]["key"] == ["gm-test-key"]
    assert req["body"]["systemInstruction"]["parts"][0]["text"]
    assert req["body"]["contents"][0]["role"] == "user"
    assert req["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert script.script["hook"] == "h"
    assert len(script.script["storyboard"]) == 5


def test_missing_api_key_raises_before_any_network_call(db_session):
    original_provider, original_key = settings.script_provider, settings.openai_api_key
    settings.script_provider = "openai"
    settings.openai_api_key = ""

    try:
        with pytest.raises(RuntimeError, match="API key is not set"):
            generate_script(db_session, topic="Missing key test topic")
    finally:
        settings.script_provider, settings.openai_api_key = original_provider, original_key
