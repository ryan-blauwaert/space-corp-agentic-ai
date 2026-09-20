from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.baselines.models import BaselineRecord
from app.equipment.models import CatalogReleaseRecord, ComponentRecord, EquipmentModelRecord, EquipmentUnitRecord, InventoryItemRecord, equipment_model_components
from app.facilities.models import FacilityRecord
from app.operations.models import IncidentRecord
from app.workspaces.models import WorkspaceRecord
from scripts.dataset_manifest import Manifest, load_manifest, operational_id, shared_id
from scripts.dataset_queries import evaluate, validate_scenarios
from scripts.seed_dataset import OPERATIONAL, publish, seed_workspace, validate_workspace
from scripts.seed_support import SeedConfigurationError

pytestmark = pytest.mark.integration


def test_seed_two_copies_refresh_and_all_canonical_evidence(integration_session: Session) -> None:
    session = integration_session
    manifest = load_manifest()
    first, second = uuid4(), uuid4()
    counts = seed_workspace(session, first, manifest)
    assert counts == dict(facilities=5, equipment_units=60, inventory_items=179, incidents=60, work_orders=60)
    assert seed_workspace(session, first, manifest) == counts
    assert seed_workspace(session, second, manifest) == counts
    assert validate_scenarios(session, first, manifest) == 12
    assert validate_scenarios(session, second, manifest) == 12
    for record in OPERATIONAL:
        first_ids = set(session.scalars(select(record.id).where(record.workspace_id == first)))
        second_ids = set(session.scalars(select(record.id).where(record.workspace_id == second)))
        assert len(first_ids) == len(second_ids) == counts[record.__tablename__]
        assert first_ids.isdisjoint(second_ids)
    baseline = session.get(BaselineRecord, session.get(WorkspaceRecord, first).baseline_id)
    original_manifest = baseline.manifest.copy()
    unit = session.get(EquipmentUnitRecord, operational_id(first, manifest.version, "units", "U001"))
    unit.operational_status = "operational"
    session.flush()
    seed_workspace(session, first, manifest)
    assert unit.operational_status == "operational"  # Normal reruns preserve edits.
    assert baseline.manifest == original_manifest
    assert validate_scenarios(session, second, manifest) == 12
    with pytest.raises(SeedConfigurationError, match="differs"):
        validate_workspace(session, first, manifest)
    seed_workspace(session, first, manifest, refresh=True)
    validate_workspace(session, first, manifest)
    assert validate_scenarios(session, first, manifest) == 12
    # Complete removal and recreation gives identical IDs and facts.
    for record in reversed(OPERATIONAL):
        session.execute(delete(record).where(record.workspace_id == first))
    session.execute(delete(WorkspaceRecord).where(WorkspaceRecord.id == first))
    session.flush()
    session.expunge_all()
    assert seed_workspace(session, first, manifest) == counts
    assert validate_scenarios(session, first, manifest) == 12
    assert validate_scenarios(session, second, manifest) == 12
    for question, inputs in (("Q1", {"facility": "missing"}), ("Q2", {"unit": "missing"}), ("Q4", {"model": "missing"})):
        with pytest.raises(SeedConfigurationError, match="does not exist|Unknown model"):
            evaluate(session, first, manifest, question, inputs)
    with pytest.raises(SeedConfigurationError, match="pinned"):
        evaluate(session, uuid4(), manifest, "Q1", {})


@pytest.mark.parametrize("change", ["model", "component", "compatibility", "baseline"])
def test_publication_rejects_rewritten_manifests(integration_session: Session, change: str) -> None:
    manifest = load_manifest()
    seed_workspace(integration_session, uuid4(), manifest)
    data = manifest.model_dump(mode="json")
    if change == "model":
        data["catalog"]["models"][0]["name"] = "Rewritten"
    elif change == "component":
        data["catalog"]["components"][0]["name"] = "Rewritten"
    elif change == "compatibility":
        data["catalog"]["compatibility"].pop()
    else:
        data["units"][0]["operational_status"] = "offline"
    with pytest.raises(SeedConfigurationError, match="Published"):
        publish(integration_session, Manifest.model_validate(data))


@pytest.mark.parametrize("change", ["model", "component", "compatibility", "addition"])
def test_publication_detects_database_catalog_drift(integration_session: Session, change: str) -> None:
    manifest = load_manifest()
    publish(integration_session, manifest)
    release = shared_id(manifest.catalog.version, "release", manifest.catalog.version)
    if change == "model":
        integration_session.get(EquipmentModelRecord, shared_id(manifest.catalog.version, "models", "M01")).name = "Drift"
    elif change == "component":
        integration_session.get(ComponentRecord, shared_id(manifest.catalog.version, "components", "C01")).name = "Drift"
    elif change == "compatibility":
        integration_session.execute(delete(equipment_model_components).where(equipment_model_components.c.catalog_release_id == release))
    else:
        integration_session.add(ComponentRecord(catalog_release_id=release, code="EXTRA", name="Extra"))
    integration_session.flush()
    with pytest.raises(SeedConfigurationError, match="Published catalog"):
        publish(integration_session, manifest)


def test_new_release_does_not_repin_or_change_existing_workspace(integration_session: Session) -> None:
    session = integration_session
    old = load_manifest()
    first, second = uuid4(), uuid4()
    seed_workspace(session, first, old)
    data = old.model_dump(mode="json")
    data["version"], data["catalog"]["version"] = "demo-2", "demo-catalog-2"
    data["catalog"]["models"][0]["name"] = "New revision"
    new = Manifest.model_validate(data)
    seed_workspace(session, second, new)
    assert validate_scenarios(session, first, old) == 12
    assert validate_scenarios(session, second, new) == 12
    with pytest.raises(SeedConfigurationError, match="pinned"):
        seed_workspace(session, first, new, refresh=True)
    workspace = session.get(WorkspaceRecord, first)
    with pytest.raises(IntegrityError, match="new workspace"):
        with session.begin_nested():
            session.execute(text("UPDATE workspaces SET baseline_id=:baseline, catalog_release_id=:release WHERE id=:workspace"), dict(baseline=shared_id(new.version,"baseline",new.version), release=shared_id(new.catalog.version,"release",new.catalog.version), workspace=first))
    # Owner inserts still respect the pin; application-role checks use a
    # separately authenticated connection in the disposable bootstrap test.
    foreign_model = shared_id(new.catalog.version, "models", "M01")
    foreign_component = shared_id(new.catalog.version, "components", "C01")
    facility = operational_id(first, old.version, "facilities", "LUN-OPS-01")
    for record in (
        EquipmentUnitRecord(workspace_id=first, facility_id=facility, equipment_model_id=foreign_model, asset_tag="FOREIGN", operational_status="operational"),
        InventoryItemRecord(workspace_id=first, facility_id=facility, component_id=foreign_component, quantity_on_hand=1, reorder_point=1),
    ):
        with pytest.raises(IntegrityError, match="workspace catalog release"):
            with session.begin_nested():
                session.add(record)
                session.flush()
    assert workspace.catalog_release_id == shared_id(old.catalog.version, "release", old.catalog.version)


def test_existing_unpinned_workspace_is_not_silently_replaced(integration_session: Session) -> None:
    workspace, facility = uuid4(), uuid4()
    integration_session.add(WorkspaceRecord(id=workspace))
    integration_session.flush()
    integration_session.add(FacilityRecord(
        id=facility, workspace_id=workspace, code="EXISTING", name="Existing Facility",
        facility_type="lunar_installation", location="Moon", operational_status="operational",
    ))
    integration_session.flush()
    with pytest.raises(SeedConfigurationError, match="not empty"):
        seed_workspace(integration_session, workspace, load_manifest(), refresh=True)
    assert integration_session.get(FacilityRecord, facility).code == "EXISTING"
    assert integration_session.get(WorkspaceRecord, workspace).baseline_id is None
