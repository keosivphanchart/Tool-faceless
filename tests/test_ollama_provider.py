"""Ollama local-LLM provider: SCRIPT_PROVIDER=ollama is the free/no-API-key
alternative to Anthropic for script generation. Since ollama.com itself is
unreachable from this sandbox (only used to install the real binary + pull
model weights on the user's own machine), this test instead stands up a
real local HTTP server that speaks Ollama's documented /api/chat contract
(POST {base_url}/api/chat -> {"message": {"content": "..."}}) and points
_call_ollama at it over a real socket, so the request shape and response
parsing are proven against an actual HTTP round-trip rather than a mock.
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


class _RecordingOllamaHandler(BaseHTTPRequestHandler):
    received_requests: list[dict] = []
    response_content = FAKE_SCRIPT_JSON
    status_code = 200

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        type(self).received_requests.append({"path": self.path, "body": body})

        self.send_response(type(self).status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {"message": {"content": type(self).response_content}}
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # silence default stderr logging
        pass


@pytest.fixture
def ollama_server():
    _RecordingOllamaHandler.received_requests = []
    _RecordingOllamaHandler.response_content = FAKE_SCRIPT_JSON
    _RecordingOllamaHandler.status_code = 200

    server = HTTPServer(("127.0.0.1", 0), _RecordingOllamaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    original_provider = settings.script_provider
    original_base_url = settings.ollama_base_url
    settings.script_provider = "ollama"
    settings.ollama_base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        yield _RecordingOllamaHandler
    finally:
        server.shutdown()
        thread.join()
        settings.script_provider = original_provider
        settings.ollama_base_url = original_base_url


def test_call_ollama_hits_api_chat_with_expected_request_shape(db_session, ollama_server):
    script = generate_script(db_session, topic="Local LLM test topic")

    assert len(ollama_server.received_requests) == 1
    req = ollama_server.received_requests[0]
    assert req["path"] == "/api/chat"
    assert req["body"]["model"] == settings.ollama_model
    assert req["body"]["format"] == "json"
    assert req["body"]["stream"] is False
    roles = [m["role"] for m in req["body"]["messages"]]
    assert roles == ["system", "user"]
    assert "Local LLM test topic" in req["body"]["messages"][1]["content"]

    assert script.script["hook"] == "h"
    assert len(script.script["storyboard"]) == 5


def test_call_ollama_malformed_json_raises(db_session, ollama_server):
    ollama_server.response_content = "not valid json {{"

    with pytest.raises(ValueError, match="malformed JSON"):
        generate_script(db_session, topic="Malformed response topic")


def test_call_ollama_connection_error_gives_actionable_message(db_session):
    original_provider = settings.script_provider
    original_base_url = settings.ollama_base_url
    settings.script_provider = "ollama"
    # Port 1 is reserved and nothing will ever listen there, so this is a
    # real (fast) connection failure, not a mocked one.
    settings.ollama_base_url = "http://127.0.0.1:1"

    try:
        with pytest.raises(RuntimeError, match="ollama serve"):
            generate_script(db_session, topic="Unreachable Ollama topic")
    finally:
        settings.script_provider = original_provider
        settings.ollama_base_url = original_base_url
