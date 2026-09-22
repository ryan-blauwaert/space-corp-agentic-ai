from unittest.mock import MagicMock, Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import (
    ApplicationStartupError,
    _verify_database_connection,
    create_app,
)

DEFAULT_WORKSPACE_ID = UUID("11111111-1111-1111-1111-111111111111")


def startup_settings(**overrides: object) -> Settings:
    """Create complete, dotenv-independent settings for lifespan tests."""
    values: dict[str, object] = {
        "database_url": "postgresql://localhost/example",
        "default_workspace_id": DEFAULT_WORKSPACE_ID,
    }
    values.update(overrides)
    return Settings(
        _env_file=None,
        **values,
    )


def test_create_app_uses_configured_name() -> None:
    application = create_app(Settings(_env_file=None, application_name="Test Operations API"))

    assert application.title == "Test Operations API"


def test_create_app_registers_api_routes() -> None:
    application = create_app(Settings(_env_file=None))
    documented_paths = application.openapi()["paths"]

    assert {"/health", "/facilities"}.issubset(documented_paths)


@pytest.mark.parametrize("fail_during_lifespan", [False, True])
def test_owned_database_is_disposed_on_shutdown(
    monkeypatch: pytest.MonkeyPatch, fail_during_lifespan: bool
) -> None:
    database = Mock()
    factory = Mock(return_value=database)
    monkeypatch.setattr("app.main.create_database", factory)
    verifier = Mock()
    monkeypatch.setattr("app.main._verify_database_connection", verifier)
    application = create_app(startup_settings())
    try:
        with TestClient(application):
            assert application.state.database is database
            if fail_during_lifespan:
                raise ValueError("simulated application failure")
    except ValueError:
        assert fail_during_lifespan
    factory.assert_called_once()
    verifier.assert_called_once_with(database)
    database.dispose.assert_called_once()
    assert application.state.database is None


def test_injected_database_remains_owned_by_caller() -> None:
    database = MagicMock()
    application = create_app(startup_settings(database_url=None), database)
    with TestClient(application):
        pass
    database.dispose.assert_not_called()


def test_startup_requires_database_configuration() -> None:
    application = create_app(Settings(_env_file=None, default_workspace_id=DEFAULT_WORKSPACE_ID))

    with pytest.raises(ApplicationStartupError, match="SPACE_CORP_DATABASE_URL"):
        with TestClient(application):
            pass


def test_startup_requires_default_workspace_id() -> None:
    application = create_app(Settings(_env_file=None), Mock())

    with pytest.raises(ApplicationStartupError, match="SPACE_CORP_DEFAULT_WORKSPACE_ID"):
        with TestClient(application):
            pass


def test_verify_database_connection_executes_health_query() -> None:
    database = MagicMock()

    _verify_database_connection(database)

    statement = database.engine.connect.return_value.__enter__.return_value.execute.call_args.args[
        0
    ]
    assert str(statement) == "SELECT 1"


def test_verify_database_connection_raises_clear_startup_error() -> None:
    database = MagicMock()
    database.engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception())

    with pytest.raises(ApplicationStartupError, match="database is unavailable"):
        _verify_database_connection(database)


def test_operational_read_openapi_and_documentation_pages() -> None:
    application = create_app(startup_settings(database_url=None), MagicMock())
    with TestClient(application) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 200
        schema = client.get("/openapi.json").json()
    paths = {
        "/equipment-models": "listEquipmentModels",
        "/components": "listComponents",
        "/equipment-units": "listEquipmentUnits",
        "/equipment-units/{equipment_unit_id}": "getEquipmentUnit",
        "/inventory-items": "listInventoryItems",
        "/inventory-items/{inventory_item_id}": "getInventoryItem",
        "/incidents": "listIncidents",
        "/incidents/{incident_id}": "getIncident",
        "/work-orders": "listWorkOrders",
        "/work-orders/{work_order_id}": "getWorkOrder",
        "/equipment-models/{equipment_model_id}": "getEquipmentModel",
        "/components/{component_id}": "getComponent",
        "/equipment-models/{equipment_model_id}/components": "listCompatibleComponents",
    }
    for path, operation_id in paths.items():
        assert set(schema["paths"][path]) == {"get"}
        operation = schema["paths"][path]["get"]
        assert operation["operationId"] == operation_id
        assert operation["tags"] == [path.split("/")[1]]
        assert "$ref" in operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert "422" in operation["responses"]
        for code in ["404", "503"] if "{" in path else ["503"]:
            assert set(operation["responses"][code]["content"]) == {"application/problem+json"}
        parameters = {p["name"]: p["schema"] for p in operation["parameters"]}
        assert "workspace_id" not in parameters
        if path in ("/equipment-models", "/components"):
            assert "catalog_release_id" in parameters
            assert "404" not in operation["responses"]
        if "{" not in path or path.endswith("/components"):
            assert parameters["limit"]["maximum"] == 100
            assert parameters["limit"]["minimum"] == 1
            assert parameters["offset"]["minimum"] == 0
    assert set(schema["paths"]) == set(paths) | {
        "/health",
        "/facilities",
        "/facilities/{facility_id}",
        "/questions",
        "/questions/confirm",
    }
