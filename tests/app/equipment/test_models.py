from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import UniqueConstraint, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import (
    CatalogReleaseRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
)
from app.facilities.models import FacilityRecord
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


def test_equipment_model_uses_release_scoped_uniqueness() -> None:
    constraints = [
        constraint
        for constraint in EquipmentModelRecord.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        tuple(constraint.columns.keys()) == ("catalog_release_id", "code")
        for constraint in constraints
    )
    assert any(
        tuple(constraint.columns.keys()) == ("catalog_release_id", "id")
        for constraint in constraints
    )


def test_equipment_unit_uses_workspace_scoped_facility_relationship() -> None:
    unit_table = EquipmentUnitRecord.__table__

    assert unit_table.c.workspace_id.nullable is False
    assert unit_table.c.facility_id.nullable is False
    assert unit_table.c.equipment_model_id.nullable is False
    assert any(
        {column.name for column in constraint.columns}
        == {"workspace_id", "facility_id"}
        for constraint in unit_table.foreign_key_constraints
    )


def test_catalog_and_workspace_relationships_are_registered() -> None:
    assert CatalogReleaseRecord.__mapper__.relationships["equipment_models"].mapper.class_ is EquipmentModelRecord
    assert EquipmentModelRecord.__mapper__.relationships["equipment_units"].mapper.class_ is EquipmentUnitRecord
    assert FacilityRecord.__mapper__.relationships["equipment_units"].mapper.class_ is EquipmentUnitRecord
    assert WorkspaceRecord.__mapper__.relationships["equipment_units"].mapper.class_ is EquipmentUnitRecord


@pytest.mark.integration
def test_catalog_and_equipment_records_generate_ids_and_timestamps(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    integration_session.add(release)
    integration_session.flush()
    model = make_equipment_model(release.id)
    integration_session.add(model)
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility(workspace.id)
    integration_session.add(facility)
    integration_session.flush()
    unit = make_equipment_unit(workspace.id, facility.id, model.id)
    integration_session.add(unit)
    integration_session.flush()
    integration_session.refresh(unit)

    assert isinstance(release.id, UUID)
    assert isinstance(release.created_at, datetime)
    assert isinstance(model.id, UUID)
    assert isinstance(model.created_at, datetime)
    assert isinstance(unit.id, UUID)
    assert isinstance(unit.created_at, datetime)
    assert isinstance(unit.updated_at, datetime)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("record_factory", "field_name", "invalid_value"),
    [
        (make_catalog_release, "code", " "),
        (make_equipment_model, "code", " "),
        (make_equipment_model, "name", ""),
        (make_equipment_unit, "asset_tag", "\u00a0\u2003"),
        (make_equipment_unit, "operational_status", "unsupported"),
    ],
)
def test_database_rejects_invalid_equipment_values(
    integration_session: Session,
    record_factory: object,
    field_name: str,
    invalid_value: str,
) -> None:
    release = make_catalog_release()
    integration_session.add(release)
    integration_session.flush()
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility(workspace.id)
    integration_session.add(facility)
    integration_session.flush()
    model = make_equipment_model(release.id)
    integration_session.add(model)
    integration_session.flush()

    if record_factory is make_catalog_release:
        record = make_catalog_release(**{field_name: invalid_value})
    elif record_factory is make_equipment_model:
        record = make_equipment_model(release.id, **{field_name: invalid_value})
    else:
        record = make_equipment_unit(
            workspace.id, facility.id, model.id, **{field_name: invalid_value}
        )
    integration_session.add(record)

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_equipment_model_code_is_unique_within_one_catalog_release(
    integration_session: Session,
) -> None:
    first_release = make_catalog_release(code="catalog-1")
    second_release = make_catalog_release(code="catalog-2")
    integration_session.add_all([first_release, second_release])
    integration_session.flush()
    integration_session.add_all(
        [
            make_equipment_model(first_release.id, code="ECS-4"),
            make_equipment_model(second_release.id, code="ECS-4"),
        ]
    )
    integration_session.flush()
    integration_session.add(make_equipment_model(first_release.id, code="ECS-4"))

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_equipment_unit_rejects_facility_from_another_workspace(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    first_workspace = WorkspaceRecord()
    second_workspace = WorkspaceRecord()
    integration_session.add_all([release, first_workspace, second_workspace])
    integration_session.flush()
    model = make_equipment_model(release.id)
    facility = make_facility(second_workspace.id)
    integration_session.add_all([model, facility])
    integration_session.flush()
    integration_session.add(
        make_equipment_unit(first_workspace.id, facility.id, model.id)
    )

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_equipment_unit_asset_tag_can_repeat_only_across_workspaces(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    first_workspace = WorkspaceRecord()
    second_workspace = WorkspaceRecord()
    integration_session.add_all([release, first_workspace, second_workspace])
    integration_session.flush()
    model = make_equipment_model(release.id)
    first_facility = make_facility(first_workspace.id, code="LUN-OPS-01")
    second_facility = make_facility(second_workspace.id, code="LUN-OPS-01")
    integration_session.add_all([model, first_facility, second_facility])
    integration_session.flush()
    integration_session.add_all(
        [
            make_equipment_unit(first_workspace.id, first_facility.id, model.id),
            make_equipment_unit(second_workspace.id, second_facility.id, model.id),
        ]
    )
    integration_session.flush()
    integration_session.add(
        make_equipment_unit(first_workspace.id, first_facility.id, model.id)
    )

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_catalog_release_delete_is_restricted_when_models_exist(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    integration_session.add(release)
    integration_session.flush()
    integration_session.add(make_equipment_model(release.id))
    integration_session.flush()

    with pytest.raises(IntegrityError):
        integration_session.execute(
            delete(CatalogReleaseRecord).where(CatalogReleaseRecord.id == release.id)
        )
