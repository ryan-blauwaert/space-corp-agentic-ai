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
from app.operations.models import IncidentRecord, WorkOrderRecord
from app.workspaces.models import WorkspaceRecord


def make_catalog_release(**overrides: object) -> CatalogReleaseRecord:
    values = {"code": "catalog-1"}
    values.update(overrides)
    return CatalogReleaseRecord(**values)


def make_equipment_model(catalog_release_id: UUID, **overrides: object) -> EquipmentModelRecord:
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
        "workspace_id": workspace_id,
        "facility_id": facility_id,
        "equipment_unit_id": equipment_unit_id,
        "reference_code": "INC-ECS-001",
        "severity": "high",
        "status": "open",
        "occurred_at": datetime.now(UTC),
        "fault_code": "AIRFLOW_LOW",
        "resolved_at": None,
    }
    values.update(overrides)
    return IncidentRecord(**values)


def make_work_order(workspace_id: UUID, facility_id: UUID, **overrides: object) -> WorkOrderRecord:
    values = {
        "workspace_id": workspace_id,
        "facility_id": facility_id,
        "originating_incident_id": None,
        "target_equipment_unit_id": None,
        "reference_code": "WO-LUN-001",
        "priority": "high",
        "status": "open",
        "due_at": None,
        "completed_at": None,
    }
    values.update(overrides)
    return WorkOrderRecord(**values)


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


def test_work_order_uses_independent_workspace_and_facility_scoped_references() -> None:
    table = WorkOrderRecord.__table__

    assert table.c.originating_incident_id.nullable is True
    assert table.c.target_equipment_unit_id.nullable is True
    assert {tuple(constraint.column_keys) for constraint in table.foreign_key_constraints} >= {
        ("workspace_id", "facility_id"),
        ("workspace_id", "facility_id", "originating_incident_id"),
        ("workspace_id", "facility_id", "target_equipment_unit_id"),
    }
    assert any(
        tuple(constraint.columns.keys()) == ("workspace_id", "reference_code")
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert {index.name for index in table.indexes} >= {
        "ix_work_orders_workspace_facility_status_priority",
        "ix_work_orders_workspace_facility_due_at",
    }


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
@pytest.mark.parametrize(
    "overrides, constraint",
    [
        ({"status": "resolved"}, "ck_incidents_resolved_at_matches_status"),
        ({"status": "unknown"}, "ck_incidents_status"),
        ({"severity": "urgent"}, "ck_incidents_severity"),
        ({"fault_code": " airflow "}, "ck_incidents_fault_code_normalized"),
        ({"fault_code": ""}, "ck_incidents_fault_code_normalized"),
        (
            {"resolved_at": datetime(2026, 1, 2, tzinfo=UTC)},
            "ck_incidents_resolved_at_matches_status",
        ),
        (
            {"status": "resolved", "resolved_at": datetime(2025, 12, 31, tzinfo=UTC)},
            "ck_incidents_resolved_at_after_occurred_at",
        ),
    ],
)
def test_incident_rejects_invalid_lifecycle_and_fault_code(
    integration_session: Session,
    overrides: dict[str, object],
    constraint: str,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility(workspace.id)
    integration_session.add(facility)
    integration_session.flush()
    integration_session.add(
        make_incident(
            workspace.id,
            facility.id,
            None,
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
            **overrides,
        )
    )

    with pytest.raises(IntegrityError) as error:
        integration_session.flush()
    assert error.value.orig.diag.constraint_name == constraint


def test_incident_relationships_are_registered() -> None:
    assert FacilityRecord.__mapper__.relationships["incidents"].mapper.class_ is IncidentRecord
    assert WorkspaceRecord.__mapper__.relationships["incidents"].mapper.class_ is IncidentRecord
    assert EquipmentUnitRecord.__mapper__.relationships["incidents"].mapper.class_ is IncidentRecord


def test_work_order_relationships_preserve_origin_and_target_meanings() -> None:
    assert FacilityRecord.__mapper__.relationships["work_orders"].mapper.class_ is WorkOrderRecord
    assert WorkspaceRecord.__mapper__.relationships["work_orders"].mapper.class_ is WorkOrderRecord
    assert (
        IncidentRecord.__mapper__.relationships["originating_work_orders"].mapper.class_
        is WorkOrderRecord
    )
    assert (
        EquipmentUnitRecord.__mapper__.relationships["targeted_work_orders"].mapper.class_
        is WorkOrderRecord
    )
    assert (
        WorkOrderRecord.__mapper__.relationships["originating_incident"].mapper.class_
        is IncidentRecord
    )
    assert (
        WorkOrderRecord.__mapper__.relationships["target_equipment_unit"].mapper.class_
        is EquipmentUnitRecord
    )


@pytest.mark.integration
@pytest.mark.parametrize("reference_kind", ["incident", "unit"])
def test_work_order_rejects_reference_from_a_different_facility(
    integration_session: Session, reference_kind: str
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
    incident = make_incident(workspace.id, first_facility.id, unit.id)
    integration_session.add(incident)
    integration_session.flush()
    values = (
        {"originating_incident_id": incident.id}
        if reference_kind == "incident"
        else {"target_equipment_unit_id": unit.id}
    )
    integration_session.add(make_work_order(workspace.id, second_facility.id, **values))

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_work_order_accepts_independent_reference_combinations(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    workspace = WorkspaceRecord()
    integration_session.add_all([release, workspace])
    integration_session.flush()
    model = make_equipment_model(release.id)
    facility = make_facility(workspace.id)
    integration_session.add_all([model, facility])
    integration_session.flush()
    unit = make_equipment_unit(workspace.id, facility.id, model.id)
    target = make_equipment_unit(workspace.id, facility.id, model.id, asset_tag="FAN-02")
    integration_session.add_all([unit, target])
    integration_session.flush()
    incident = make_incident(workspace.id, facility.id, unit.id)
    integration_session.add(incident)
    integration_session.flush()
    records = [
        make_work_order(workspace.id, facility.id, reference_code="WO-001"),
        make_work_order(
            workspace.id, facility.id, reference_code="WO-002", target_equipment_unit_id=unit.id
        ),
        make_work_order(
            workspace.id, facility.id, reference_code="WO-003", originating_incident_id=incident.id
        ),
        make_work_order(
            workspace.id,
            facility.id,
            reference_code="WO-004",
            originating_incident_id=incident.id,
            target_equipment_unit_id=unit.id,
        ),
        make_work_order(
            workspace.id,
            facility.id,
            reference_code="WO-005",
            originating_incident_id=incident.id,
            target_equipment_unit_id=target.id,
        ),
    ]
    integration_session.add_all(records)
    integration_session.flush()
    integration_session.expire_all()
    assert records[2].target_equipment_unit is None
    assert records[4].originating_incident.equipment_unit.id == unit.id
    assert records[4].target_equipment_unit.id == target.id
    assert records[4].facility.id == facility.id


@pytest.mark.integration
@pytest.mark.parametrize(
    "overrides, constraint",
    [
        ({"reference_code": "\u2003"}, "ck_work_orders_reference_code_not_blank"),
        ({"priority": "urgent"}, "ck_work_orders_priority"),
        ({"status": "unknown"}, "ck_work_orders_status"),
        ({"status": "completed"}, "ck_work_orders_completed_at_matches_status"),
        (
            {"completed_at": datetime(2026, 1, 2, tzinfo=UTC)},
            "ck_work_orders_completed_at_matches_status",
        ),
        (
            {"status": "cancelled", "completed_at": datetime(2026, 1, 2, tzinfo=UTC)},
            "ck_work_orders_completed_at_matches_status",
        ),
        (
            {"status": "completed", "completed_at": datetime(2025, 12, 31, tzinfo=UTC)},
            "ck_work_orders_completed_at_after_created_at",
        ),
    ],
)
def test_database_rejects_invalid_work_order_lifecycle(
    integration_session: Session, overrides: dict[str, object], constraint: str
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility(workspace.id)
    integration_session.add(facility)
    integration_session.flush()
    record = make_work_order(
        workspace.id, facility.id, created_at=datetime(2026, 1, 1, tzinfo=UTC), **overrides
    )
    integration_session.add(record)
    with pytest.raises(IntegrityError) as error:
        integration_session.flush()
    assert error.value.orig.diag.constraint_name == constraint


@pytest.mark.integration
def test_work_order_completion_boundary_and_scoped_uniqueness(
    integration_session: Session,
) -> None:
    workspaces = [WorkspaceRecord(), WorkspaceRecord()]
    integration_session.add_all(workspaces)
    integration_session.flush()
    facilities = [make_facility(workspace.id) for workspace in workspaces]
    integration_session.add_all(facilities)
    integration_session.flush()
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    for facility in facilities:
        integration_session.add(
            make_work_order(
                facility.workspace_id,
                facility.id,
                status="completed",
                created_at=instant,
                completed_at=instant,
            )
        )
    integration_session.flush()
    integration_session.add(make_work_order(workspaces[0].id, facilities[0].id))
    with pytest.raises(IntegrityError) as error:
        integration_session.flush()
    assert error.value.orig.diag.constraint_name == "uq_work_orders_workspace_reference_code"
