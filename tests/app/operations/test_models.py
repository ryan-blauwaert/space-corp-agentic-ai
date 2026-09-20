from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import (
    CatalogReleaseRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
)
from app.facilities.models import FacilityRecord
from app.operations.models import IncidentRecord
from app.workspaces.models import WorkspaceRecord


def make_catalog_release(**overrides: object) -> CatalogReleaseRecord:
    values = {"code": "catalog-1"}
    values.update(overrides)
    return CatalogReleaseRecord(**values)


def make_equipment_model(
    catalog_release_id: UUID, **overrides: object
) -> EquipmentModelRecord:
    values = {
        "catalog_release_id": catalog_release_id,
        "code": "ECS-4",
        "name": "Environmental Control System 4",
    }
    values.update(overrides)
    return EquipmentModelRecord(**values)


def make_facility(workspace_id: UUID, **overrides: object) -> FacilityRecord:
    values = {
        "workspace_id": workspace_id,
        "code": "LUN-OPS-01",
        "name": "Lunar Operations One",
        "facility_type": "lunar_installation",
        "location": "Mare Imbrium",
        "operational_status": "operational",
    }
    values.update(overrides)
    return FacilityRecord(**values)


def make_equipment_unit(
    workspace_id: UUID,
    facility_id: UUID,
    equipment_model_id: UUID,
    **overrides: object,
) -> EquipmentUnitRecord:
    values = {
        "workspace_id": workspace_id,
        "facility_id": facility_id,
        "equipment_model_id": equipment_model_id,
        "asset_tag": "ECS-14",
        "operational_status": "operational",
    }
    values.update(overrides)
    return EquipmentUnitRecord(**values)


def make_incident(
    workspace_id: UUID, facility_id: UUID, equipment_unit_id: UUID | None, **overrides: object
) -> IncidentRecord:
    values = {
        "workspace_id": workspace_id, "facility_id": facility_id,
        "equipment_unit_id": equipment_unit_id, "reference_code": "INC-ECS-001",
        "severity": "high", "status": "open", "occurred_at": datetime.now(UTC),
        "fault_code": "AIRFLOW_LOW", "resolved_at": None,
    }
    values.update(overrides)
    return IncidentRecord(**values)


def test_incident_uses_workspace_and_facility_scoped_equipment_relationship() -> None:
    incident_table = IncidentRecord.__table__

    assert incident_table.c.equipment_unit_id.nullable is True
    assert any(
        {column.name for column in constraint.columns}
        == {"workspace_id", "facility_id", "equipment_unit_id"}
        for constraint in incident_table.foreign_key_constraints
    )
    assert any(
        tuple(constraint.columns.keys()) == ("workspace_id", "reference_code")
        for constraint in incident_table.constraints
        if isinstance(constraint, UniqueConstraint)
    )


@pytest.mark.integration
def test_incident_rejects_unit_at_a_different_facility(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    workspace = WorkspaceRecord()
    integration_session.add_all([release, workspace])
    integration_session.flush()
    model = make_equipment_model(release.id)
    first_facility = make_facility(workspace.id)
    second_facility = make_facility(workspace.id, code="ORB-OPS-01")
    integration_session.add_all([model, first_facility, second_facility])
    integration_session.flush()
    unit = make_equipment_unit(workspace.id, first_facility.id, model.id)
    integration_session.add(unit)
    integration_session.flush()
    integration_session.add(make_incident(workspace.id, second_facility.id, unit.id))

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_incident_rejects_invalid_lifecycle_and_fault_code(
    integration_session: Session,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility(workspace.id)
    integration_session.add(facility)
    integration_session.flush()
    integration_session.add(
        make_incident(
            workspace.id, facility.id, None, status="resolved", resolved_at=None
        )
    )

    with pytest.raises(IntegrityError):
        integration_session.flush()


def test_incident_relationships_are_registered() -> None:
    assert FacilityRecord.__mapper__.relationships["incidents"].mapper.class_ is IncidentRecord
    assert WorkspaceRecord.__mapper__.relationships["incidents"].mapper.class_ is IncidentRecord
    assert EquipmentUnitRecord.__mapper__.relationships["incidents"].mapper.class_ is IncidentRecord
