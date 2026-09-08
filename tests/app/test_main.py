from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.database import Database
from app.config import Settings
from app.main import create_app


def test_create_app_uses_configured_name() -> None:
    application = create_app(Settings(application_name="Test Operations API"))

    assert application.title == "Test Operations API"


def test_create_app_registers_api_routes() -> None:
    application = create_app()
    documented_paths = application.openapi()["paths"]

    assert {"/health", "/facilities"}.issubset(documented_paths)


@pytest.mark.parametrize("fail_during_lifespan", [False, True])
def test_owned_database_is_disposed_on_shutdown(
    monkeypatch: pytest.MonkeyPatch, fail_during_lifespan: bool
) -> None:
    database = Mock(spec=Database)
    factory = Mock(return_value=database)
    monkeypatch.setattr("app.main.create_database", factory)
    application = create_app(Settings(database_url="postgresql://localhost/example"))
    try:
        with TestClient(application):
            assert application.state.database is database
            if fail_during_lifespan:
                raise ValueError("simulated application failure")
    except ValueError:
        assert fail_during_lifespan
    factory.assert_called_once()
    database.dispose.assert_called_once()
    assert application.state.database is None


def test_injected_database_remains_owned_by_caller() -> None:
    database = Mock(spec=Database)
    with TestClient(create_app(Settings(database_url=None), database)):
        pass
    database.dispose.assert_not_called()
