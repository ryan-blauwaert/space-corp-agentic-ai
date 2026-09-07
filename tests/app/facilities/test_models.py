from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import UniqueConstraint, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.facilities.models import FacilityRecord
from app.workspaces.models import WorkspaceRecord


def test_facility_record_has_explicit_workspace_ownership() -> None:
    facility_table = FacilityRecord.__table__

    assert facility_table.c.workspace_id.nullable is False
    assert facility_table.c.workspace_id.foreign_keys
    assert facility_table.c.workspace_id.index is True


def test_facility_code_is_unique_within_a_workspace() -> None:
    facility_table = FacilityRecord.__table__
    unique_constraints = [
        constraint
        for constraint in facility_table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        tuple(constraint.columns.keys()) == ("workspace_id", "code")
        for constraint in unique_constraints
    )


def test_workspace_record_exposes_facility_relationship() -> None:
    relationship = WorkspaceRecord.__mapper__.relationships["facilities"]

    assert relationship.mapper.class_ is FacilityRecord


def make_facility_record(workspace_id: UUID, **overrides: object) -> FacilityRecord:
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


@pytest.mark.integration
def test_workspace_record_generates_identifier_and_timestamp(
    integration_session: Session,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()

    assert isinstance(workspace.id, UUID)
    assert isinstance(workspace.created_at, datetime)


@pytest.mark.integration
def test_facility_record_generates_identifiers_and_timestamps(
    integration_session: Session,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility_record(workspace.id)
    integration_session.add(facility)
    integration_session.flush()
    integration_session.refresh(facility)

    assert isinstance(facility.id, UUID)
    assert isinstance(facility.created_at, datetime)
    assert isinstance(facility.updated_at, datetime)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("code", ""),
        ("name", ""),
        ("location", ""),
        ("facility_type", "unsupported_type"),
        ("operational_status", "unsupported_status"),
    ],
)
def test_facility_database_rejects_invalid_constraint_values(
    integration_session: Session,
    field_name: str,
    invalid_value: str,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    integration_session.add(
        make_facility_record(workspace.id, **{field_name: invalid_value})
    )

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_facility_database_rejects_unknown_workspace(
    integration_session: Session,
) -> None:
    integration_session.add(make_facility_record(uuid4()))

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
@pytest.mark.parametrize(
    "field_name",
    [
        "workspace_id",
        "code",
        "name",
        "facility_type",
        "location",
        "operational_status",
    ],
)
def test_facility_database_rejects_null_required_values(
    integration_session: Session,
    field_name: str,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility_record(workspace.id)
    setattr(facility, field_name, None)
    integration_session.add(facility)

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_facility_code_is_unique_only_within_its_workspace(
    integration_session: Session,
) -> None:
    first_workspace = WorkspaceRecord()
    second_workspace = WorkspaceRecord()
    integration_session.add_all([first_workspace, second_workspace])
    integration_session.flush()
    integration_session.add_all(
        [
            make_facility_record(first_workspace.id),
            make_facility_record(second_workspace.id),
        ]
    )

    integration_session.flush()


@pytest.mark.integration
def test_facility_database_rejects_duplicate_code_in_one_workspace(
    integration_session: Session,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    integration_session.add_all(
        [make_facility_record(workspace.id), make_facility_record(workspace.id)]
    )

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_workspace_delete_is_restricted_when_facilities_exist(
    integration_session: Session,
) -> None:
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    integration_session.add(make_facility_record(workspace.id))
    integration_session.flush()

    with pytest.raises(IntegrityError):
        integration_session.execute(
            delete(WorkspaceRecord).where(WorkspaceRecord.id == workspace.id)
        )
