from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.equipment.domain import (
    EquipmentModel,
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
from app.operations.domain import IncidentSeverity, IncidentStatus, NewIncident
from app.operations.repository import SqlAlchemyIncidentRepository
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


def create_model(integration_session: Session) -> EquipmentModel:
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


@pytest.mark.integration
def test_incident_repository_supports_facility_only_incidents(
    integration_session: Session, workspace_id: UUID
) -> None:
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    repository = SqlAlchemyIncidentRepository(integration_session)

    created = repository.create(workspace_id, make_new_incident(facility.id, None))

    assert created.equipment_unit_id is None
    assert repository.get_by_id(workspace_id, created.id) == created
    assert repository.list_by_facility(workspace_id, facility.id) == [created]
    assert repository.count_by_facility(workspace_id, facility.id) == 1


@pytest.mark.integration
def test_incident_repository_excludes_another_workspace(
    integration_session: Session, workspace_id: UUID
) -> None:
    other_workspace = WorkspaceRecord(id=uuid4())
    integration_session.add(other_workspace)
    integration_session.flush()
    facility = SqlAlchemyFacilityRepository(integration_session).create(
        workspace_id, make_new_facility()
    )
    repository = SqlAlchemyIncidentRepository(integration_session)
    created = repository.create(workspace_id, make_new_incident(facility.id, None))

    assert repository.get_by_id(other_workspace.id, created.id) is None
    assert repository.list_by_facility(other_workspace.id, facility.id) == []
    assert repository.count_by_facility(other_workspace.id, facility.id) == 0
    assert repository.update_lifecycle(
        other_workspace.id,
        created.id,
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.RESOLVED,
        resolved_at=datetime.now(UTC),
    ) is None
    assert repository.get_by_id(workspace_id, created.id) == created
