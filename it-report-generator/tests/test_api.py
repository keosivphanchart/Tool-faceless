from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

CSV = b"server,status,cpu,ram,disk\nServer01,up,92,40,55\nServer02,down,,,\n"


def test_analyze_returns_summary_and_persists_pdf():
    with TestClient(app) as client:
        resp = client.post("/api/analyze", files={"file": ("servers.csv", CSV, "text/csv")})

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total_servers"] == 2
        assert body["summary"]["critical"] == 2
        assert "id" in body

        pdf_resp = client.get(f"/api/reports/{body['id']}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert pdf_resp.content[:4] == b"%PDF"


def test_analyze_with_bad_file_returns_400():
    with TestClient(app) as client:
        resp = client.post("/api/analyze", files={"file": ("servers.csv", b"not,a,csv\nno server column", "text/csv")})
        assert resp.status_code == 400


def test_list_and_get_report():
    with TestClient(app) as client:
        created = client.post("/api/analyze", files={"file": ("servers.csv", CSV, "text/csv")}).json()

        listed = client.get("/api/reports").json()
        assert any(r["id"] == created["id"] for r in listed)

        fetched = client.get(f"/api/reports/{created['id']}").json()
        assert fetched["summary"]["total_servers"] == 2


def test_get_missing_report_returns_404():
    with TestClient(app) as client:
        assert client.get("/api/reports/999999").status_code == 404


def test_send_email_without_config_returns_400():
    with TestClient(app) as client:
        created = client.post("/api/analyze", files={"file": ("servers.csv", CSV, "text/csv")}).json()
        resp = client.post(f"/api/reports/{created['id']}/send-email")
        assert resp.status_code == 400


def test_send_email_with_config_calls_delivery():
    with TestClient(app) as client:
        created = client.post("/api/analyze", files={"file": ("servers.csv", CSV, "text/csv")}).json()
        with patch("app.main.send_email") as mock_send:
            resp = client.post(f"/api/reports/{created['id']}/send-email")
        assert resp.status_code == 200
        assert resp.json() == {"sent": True}
        mock_send.assert_called_once()


def test_send_telegram_with_config_calls_delivery():
    with TestClient(app) as client:
        created = client.post("/api/analyze", files={"file": ("servers.csv", CSV, "text/csv")}).json()
        with patch("app.main.send_telegram") as mock_send:
            resp = client.post(f"/api/reports/{created['id']}/send-telegram")
        assert resp.status_code == 200
        mock_send.assert_called_once()
