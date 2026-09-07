from sqlalchemy import UniqueConstraint

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
