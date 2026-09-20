from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.config import Settings
from app.database import Database
from app.equipment.models import EquipmentUnitRecord, InventoryItemRecord
from app.main import create_app
from scripts.bootstrap_development import bootstrap, ROOT
from scripts.dataset_manifest import Manifest, load_manifest, operational_id, shared_id
from scripts.seed_dataset import seed_workspace
from scripts.seed_support import SeedConfigurationError, require_migration_owner
from tests.scripts.test_provision_postgresql_application_role import provisioning_cluster, provision


@pytest.mark.parametrize("overrides", [
    {"environment": "production"}, {"migration_database_url": None},
    {"migration_database_url": "postgresql+psycopg://space_corp@localhost/space_corp_test"},
    {"migration_database_url": "postgresql+psycopg://space_corp@remote.example/space_corp"},
    {"migration_database_url": "postgresql+psycopg://space_corp@localhost/space_corp?host=remote.example"},
    {"default_workspace_id": None},
])
def test_bootstrap_guards_precede_migrations(monkeypatch: pytest.MonkeyPatch, overrides: dict[str, object]) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Unsafe settings must not reach migrations")
    monkeypatch.setattr(command, "upgrade", forbidden)
    settings = Settings(_env_file=None, environment="development", migration_database_url="postgresql+psycopg://space_corp@localhost/space_corp", default_workspace_id=uuid4()).model_copy(update=overrides)
    with pytest.raises(SeedConfigurationError):
        bootstrap(settings)


@pytest.mark.integration
def test_bootstrap_from_scratch_pins_and_existing_facility_api(
    provisioning_cluster: tuple[Path, dict[str, str]],
) -> None:
    _, environment = provisioning_cluster
    url = URL.create("postgresql+psycopg", username="space_corp", host="localhost", database="space_corp", query={"host": environment["PGHOST"], "port": environment["PGPORT"]})
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["migration_database_url"] = url.render_as_string(hide_password=False)
    command.downgrade(config, "base")
    empty_database = Database(url.render_as_string(hide_password=False))
    try:
        with empty_database.session() as session:
            with pytest.raises(SeedConfigurationError, match="migrations must be applied"):
                require_migration_owner(session)
    finally:
        empty_database.dispose()
    workspace = uuid4()
    settings = Settings(_env_file=None, environment="development", migration_database_url=url.render_as_string(hide_password=False), default_workspace_id=workspace)
    result = bootstrap(settings, validate=True)
    assert result["scenarios_verified"] == 12
    assert bootstrap(settings, validate=True) == result
    assert bootstrap(settings, refresh=True) == result
    # Initial role provisioning is administrative and separate from repeatable bootstrap.
    assert provision(provisioning_cluster).returncode == 0
    assert bootstrap(settings, validate=True) == result
    owner = Database(str(settings.migration_database_url))
    application_url = url.set(username="space_corp_app").render_as_string(hide_password=False)
    application = Database(application_url)
    manifest = load_manifest()
    newer = manifest.model_dump(mode="json")
    newer["version"], newer["catalog"]["version"] = "demo-2", "demo-catalog-2"
    newer = Manifest.model_validate(newer)
    other_workspace = uuid4()
    try:
        with owner.session() as session:
            seed_workspace(session, other_workspace, newer)
        facility = operational_id(workspace, manifest.version, "facilities", "LUN-OPS-01")
        with application.workspace_session(workspace) as session:
            assert session.scalar(text("SELECT current_user")) == "space_corp_app"
            assert len(session.scalars(select(EquipmentUnitRecord)).all()) == 60
            for record in (
                EquipmentUnitRecord(workspace_id=workspace, facility_id=facility, equipment_model_id=shared_id(newer.catalog.version, "models", "M01"), asset_tag="FOREIGN", operational_status="operational"),
                InventoryItemRecord(workspace_id=workspace, facility_id=facility, component_id=shared_id(newer.catalog.version, "components", "C01"), quantity_on_hand=1, reorder_point=1),
            ):
                with pytest.raises(IntegrityError, match="workspace catalog release"):
                    with session.begin_nested():
                        session.add(record)
                        session.flush()
            with pytest.raises(ProgrammingError):
                with session.begin_nested():
                    session.execute(text("UPDATE workspaces SET baseline_id=NULL, catalog_release_id=NULL"))
            with pytest.raises(ProgrammingError):
                with session.begin_nested():
                    session.execute(text("UPDATE baselines SET version='rewritten'"))
            # Successful same-release inserts ensure the definer trigger works with
            # a role that cannot SELECT the workspace table itself.
            session.add(EquipmentUnitRecord(workspace_id=workspace, facility_id=facility,
                equipment_model_id=shared_id(manifest.catalog.version, "models", "M01"),
                asset_tag="ADDED", operational_status="operational"))
            session.flush()
        api_settings = Settings(_env_file=None, environment="development", database_url=application_url, default_workspace_id=workspace)
        with TestClient(create_app(settings=api_settings)) as client:
            response = client.get("/facilities")
            assert response.status_code == 200
            assert response.json()["pagination"]["total"] == 5
            assert client.get(f"/facilities/{facility}").status_code == 200
            foreign = operational_id(other_workspace, newer.version, "facilities", "LUN-OPS-01")
            assert client.get(f"/facilities/{foreign}").status_code == 404
        assert bootstrap(settings, refresh=True) == result
    finally:
        application.dispose()
        owner.dispose()
