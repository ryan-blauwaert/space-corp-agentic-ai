from uuid import uuid4
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_http_problem_preserves_method_allow_header() -> None:
    application = create_app(
        Settings(_env_file=None, database_url=None, default_workspace_id=uuid4()),
        MagicMock(),
    )

    with TestClient(application) as client:
        response = client.post("/health")
    assert response.status_code == 405
    assert response.headers["allow"] == "GET"
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Method Not Allowed"
    assert response.json()["instance"] == "/health"
