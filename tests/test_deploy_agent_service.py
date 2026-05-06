from fastapi.testclient import TestClient

from deploy.agent_service.app import app


def test_health_returns_sdk_version() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["agents_sdk_version"]


def test_index_returns_chat_ui() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Realtime Demo" in response.text
    assert "Connect" in response.text


def test_realtime_app_js_uses_current_host() -> None:
    client = TestClient(app)

    response = client.get("/app.js")

    assert response.status_code == 200
    assert "window.location.host" in response.text
    assert "localhost:8000" not in response.text


def test_run_reports_missing_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post("/run", json={"message": "hello"})

    assert response.status_code == 500
    assert response.json()["detail"] == "OPENAI_API_KEY is not configured."
