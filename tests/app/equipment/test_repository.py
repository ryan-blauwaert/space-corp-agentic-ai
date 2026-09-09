from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.domain import (
    EquipmentOperationalStatus,
    NewCatalogRelease,
    NewEquipmentModel,
    NewEquipmentUnit,
)
from app.equipment.repository import (
    SqlAlchemyCatalogRepository,
    SqlAlchemyEquipmentUnitRepository,
)
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


def make_new_equipment_unit(
    facility_id: UUID, equipment_model_id: UUID, asset_tag: str = "ECS-14"
) -> NewEquipmentUnit:
    return NewEquipmentUnit(
        facility_id=facility_id,
        equipment_model_id=equipment_model_id,
        asset_tag=asset_tag,
        operational_status=EquipmentOperationalStatus.DEGRADED,
    )


@pytest.mark.integration
def test_catalog_repository_creates_and_retrieves_model(
    integration_session: Session,
) -> None:
    model = create_model(integration_session)
    repository = SqlAlchemyCatalogRepository(integration_session)

    assert repository.get_model_by_id(model.id) == model


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
