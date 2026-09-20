from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.domain import (
    EquipmentOperationalStatus,
    IncidentSeverity,
    IncidentStatus,
    NewCatalogRelease,
    NewComponent,
    NewEquipmentModel,
    NewEquipmentUnit,
    NewInventoryItem,
    NewIncident,
)
from app.equipment.repository import (
    SqlAlchemyCatalogRepository,
    SqlAlchemyEquipmentUnitRepository,
    SqlAlchemyInventoryItemRepository,
    SqlAlchemyIncidentRepository,
)
from app.equipment.models import EquipmentModelRecord
from app.facilities.domain import FacilityOperationalStatus, FacilityType, NewFacility
from app.facilities.repository import SqlAlchemyFacilityRepository
from app.workspaces.models import WorkspaceRecord


@pytest.fixture
def workspace_id(integration_session: Session) -> UUID:
    workspace = WorkspaceRecord(id=uuid4())
    integration_session.add(workspace)
    integration_session.flush()
    return workspace.id


def make_new_facility(code: str = "LUN-OPS-01") -> NewFacility:
    return NewFacility(
        code=code,
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )


def create_model(integration_session: Session):
    catalog = SqlAlchemyCatalogRepository(integration_session)
    release = catalog.create_release(NewCatalogRelease(code="catalog-1"))
    return catalog.create_model(
        NewEquipmentModel(
            catalog_release_id=release.id,
            code="ECS-4",
            name="Environmental Control System 4",
        )
    )


def create_component(integration_session: Session, catalog_release_id: UUID):
    return SqlAlchemyCatalogRepository(integration_session).create_component(
        NewComponent(
            catalog_release_id=catalog_release_id,
            code="FLT-F12",
            name="Air Filter F-12",
        )
    )


def make_new_equipment_unit(
    facility_id: UUID, equipment_model_id: UUID, asset_tag: str = "ECS-14"
) -> NewEquipmentUnit:
    return NewEquipmentUnit(
        facility_id=facility_id,
        equipment_model_id=equipment_model_id,
        asset_tag=asset_tag,
        operational_status=EquipmentOperationalStatus.DEGRADED,
    )


def create_component_for_inventory(integration_session: Session) -> UUID:
    catalog = SqlAlchemyCatalogRepository(integration_session)
    release = catalog.create_release(NewCatalogRelease(code="catalog-1"))
    return create_component(integration_session, release.id).id


def make_new_inventory_item(
    facility_id: UUID,
    component_id: UUID,
    *,
    quantity_on_hand: int = 0,
    reorder_point: int = 2,
) -> NewInventoryItem:
    return NewInventoryItem(
        facility_id=facility_id,
        component_id=component_id,
        quantity_on_hand=quantity_on_hand,
        reorder_point=reorder_point,
    )


def make_new_incident(facility_id: UUID, equipment_unit_id: UUID | None) -> NewIncident:
    return NewIncident(
        facility_id=facility_id,
        equipment_unit_id=equipment_unit_id,
        reference_code="INC-ECS-001",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        occurred_at=datetime.now(UTC) - timedelta(hours=1),
        fault_code="AIRFLOW_LOW",
    )


@pytest.mark.integration
def test_catalog_repository_creates_and_retrieves_model(
    integration_session: Session,
) -> None:
    model = create_model(integration_session)
    repository = SqlAlchemyCatalogRepository(integration_session)

    assert repository.get_model_by_id(model.id) == model


@pytest.mark.integration
def test_catalog_repository_creates_components_and_links_same_release_revisions(
    integration_session: Session,
) -> None:
    repository = SqlAlchemyCatalogRepository(integration_session)
    release = repository.create_release(NewCatalogRelease(code="catalog-1"))
    model = repository.create_model(
        NewEquipmentModel(
            catalog_release_id=release.id,
            code="ECS-4",
            name="Environmental Control System 4",
        )
    )
    component = create_component(integration_session, release.id)

    repository.link_model_to_component(release.id, model.id, component.id)

    assert repository.get_component_by_id(component.id) == component
    persisted_model = integration_session.get(EquipmentModelRecord, model.id)
    assert persisted_model is not None
    assert [record.id for record in persisted_model.components] == [component.id]


@pytest.mark.integration
def test_catalog_repository_rejects_mixed_release_compatibility(
    integration_session: Session,
) -> None:
    repository = SqlAlchemyCatalogRepository(integration_session)
    first_release = repository.create_release(NewCatalogRelease(code="catalog-1"))
    second_release = repository.create_release(NewCatalogRelease(code="catalog-2"))
    model = repository.create_model(
        NewEquipmentModel(
            catalog_release_id=first_release.id,
            code="ECS-4",
            name="Environmental Control System 4",
        )
    )
    component = create_component(integration_session, second_release.id)

    with pytest.raises(IntegrityError):
        repository.link_model_to_component(first_release.id, model.id, component.id)


@pytest.mark.integration
def test_equipment_unit_repository_creates_and_retrieves_unit(
    integration_session: Session, workspace_id: UUID
) -> None:
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    model = create_model(integration_session)
    repository = SqlAlchemyEquipmentUnitRepository(integration_session)

    created = repository.create(
        workspace_id, make_new_equipment_unit(facility.id, model.id)
    )

    assert repository.get_by_id(workspace_id, created.id) == created
    assert created.created_at is not None
    assert created.updated_at is not None


@pytest.mark.integration
def test_equipment_unit_repository_lists_a_facility_page_and_count(
    integration_session: Session, workspace_id: UUID
) -> None:
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    model = create_model(integration_session)
    repository = SqlAlchemyEquipmentUnitRepository(integration_session)
    repository.create(workspace_id, make_new_equipment_unit(facility.id, model.id, "ECS-20"))
    repository.create(workspace_id, make_new_equipment_unit(facility.id, model.id, "ECS-10"))
    repository.create(workspace_id, make_new_equipment_unit(facility.id, model.id, "ECS-30"))

    units = repository.list_by_facility(workspace_id, facility.id, limit=2, offset=1)

    assert [unit.asset_tag for unit in units] == ["ECS-20", "ECS-30"]
    assert repository.count_by_facility(workspace_id, facility.id) == 3


@pytest.mark.integration
def test_equipment_unit_repository_excludes_another_workspaces_unit(
    integration_session: Session, workspace_id: UUID
) -> None:
    other_workspace_id = uuid4()
    integration_session.add(WorkspaceRecord(id=other_workspace_id))
    integration_session.flush()
    facility_repository = SqlAlchemyFacilityRepository(integration_session)
    other_facility = facility_repository.create(
        other_workspace_id, make_new_facility("ORB-OPS-01")
    )
    model = create_model(integration_session)
    repository = SqlAlchemyEquipmentUnitRepository(integration_session)
    other_unit = repository.create(
        other_workspace_id, make_new_equipment_unit(other_facility.id, model.id)
    )

    assert repository.get_by_id(workspace_id, other_unit.id) is None
    assert repository.list_by_facility(workspace_id, other_facility.id) == []
    assert (
        repository.update_operational_status(
            workspace_id, other_unit.id, EquipmentOperationalStatus.OFFLINE
        )
        is None
    )


@pytest.mark.integration
def test_equipment_unit_repository_updates_only_operational_status(
    integration_session: Session, workspace_id: UUID
) -> None:
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    model = create_model(integration_session)
    repository = SqlAlchemyEquipmentUnitRepository(integration_session)
    created = repository.create(
        workspace_id, make_new_equipment_unit(facility.id, model.id)
    )

    updated = repository.update_operational_status(
        workspace_id, created.id, EquipmentOperationalStatus.OFFLINE
    )

    assert updated is not None
    assert updated.operational_status is EquipmentOperationalStatus.OFFLINE
    assert updated.asset_tag == created.asset_tag
    assert updated.facility_id == created.facility_id
    assert updated.equipment_model_id == created.equipment_model_id


@pytest.mark.integration
def test_equipment_unit_repository_propagates_scoped_facility_constraint(
    integration_session: Session, workspace_id: UUID
) -> None:
    other_workspace_id = uuid4()
    integration_session.add(WorkspaceRecord(id=other_workspace_id))
    integration_session.flush()
    other_facility = SqlAlchemyFacilityRepository(integration_session).create(
        other_workspace_id, make_new_facility("ORB-OPS-01")
    )
    model = create_model(integration_session)

    with pytest.raises(IntegrityError):
        SqlAlchemyEquipmentUnitRepository(integration_session).create(
            workspace_id, make_new_equipment_unit(other_facility.id, model.id)
        )


@pytest.mark.integration
def test_inventory_repository_creates_lists_and_updates_stock(
    integration_session: Session, workspace_id: UUID
) -> None:
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    component_id = create_component_for_inventory(integration_session)
    repository = SqlAlchemyInventoryItemRepository(integration_session)

    created = repository.create(
        workspace_id,
        make_new_inventory_item(facility.id, component_id),
    )
    updated = repository.update_stock_levels(
        workspace_id,
        created.id,
        quantity_on_hand=4,
        reorder_point=5,
    )

    assert updated is not None
    assert updated.quantity_on_hand == 4
    assert updated.reorder_point == 5
    assert updated.component_id == component_id
    assert repository.get_by_id(workspace_id, created.id) == updated
    assert repository.list_by_facility(workspace_id, facility.id) == [updated]
    assert repository.count_by_facility(workspace_id, facility.id) == 1


@pytest.mark.integration
def test_inventory_repository_excludes_another_workspace(
    integration_session: Session, workspace_id: UUID
) -> None:
    other_workspace_id = uuid4()
    integration_session.add(WorkspaceRecord(id=other_workspace_id))
    integration_session.flush()
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        other_workspace_id, make_new_facility("ORB-OPS-01")
    )
    component_id = create_component_for_inventory(integration_session)
    repository = SqlAlchemyInventoryItemRepository(integration_session)
    other_item = repository.create(
        other_workspace_id,
        make_new_inventory_item(facility.id, component_id),
    )

    assert repository.get_by_id(workspace_id, other_item.id) is None
    assert repository.list_by_facility(workspace_id, facility.id) == []
    assert repository.update_stock_levels(
        workspace_id,
        other_item.id,
        quantity_on_hand=4,
        reorder_point=5,
    ) is None


@pytest.mark.integration
def test_inventory_repository_validates_stock_updates(
    integration_session: Session, workspace_id: UUID
) -> None:
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    component_id = create_component_for_inventory(integration_session)
    repository = SqlAlchemyInventoryItemRepository(integration_session)
    created = repository.create(
        workspace_id,
        make_new_inventory_item(facility.id, component_id),
    )

    with pytest.raises(ValueError, match="Quantity on hand must not be negative"):
        repository.update_stock_levels(
            workspace_id,
            created.id,
            quantity_on_hand=-1,
            reorder_point=2,
        )


@pytest.mark.integration
def test_incident_repository_creates_lists_and_resolves_an_incident(
    integration_session: Session, workspace_id: UUID
) -> None:
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    model = create_model(integration_session)
    unit = SqlAlchemyEquipmentUnitRepository(integration_session).create(
        workspace_id, make_new_equipment_unit(facility.id, model.id)
    )
    repository = SqlAlchemyIncidentRepository(integration_session)
    created = repository.create(workspace_id, make_new_incident(facility.id, unit.id))

    resolved_at = datetime.now(UTC)
    updated = repository.update_lifecycle(
        workspace_id, created.id, severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.RESOLVED, resolved_at=resolved_at,
    )

    assert updated is not None
    assert updated.status is IncidentStatus.RESOLVED
    assert updated.severity is IncidentSeverity.CRITICAL
    assert updated.resolved_at == resolved_at
    assert updated.reference_code == "INC-ECS-001"
    assert repository.get_by_id(workspace_id, created.id) == updated
    assert repository.list_by_facility(workspace_id, facility.id) == [updated]
    assert repository.count_by_facility(workspace_id, facility.id) == 1
