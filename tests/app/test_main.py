import importlib

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app import main
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_application_uses_configured_name(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SPACE_CORP_APPLICATION_NAME", "Test Operations API")

    try:
        importlib.reload(main)

        assert main.app.title == "Test Operations API"
    finally:
        monkeypatch.undo()
        importlib.reload(main)
