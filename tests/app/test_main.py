from app.config import Settings
from app.main import create_app


def test_create_app_uses_configured_name() -> None:
    application = create_app(Settings(application_name="Test Operations API"))

    assert application.title == "Test Operations API"


def test_create_app_registers_api_routes() -> None:
    application = create_app()
    documented_paths = application.openapi()["paths"]

    assert {"/health", "/facilities"}.issubset(documented_paths)
