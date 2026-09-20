from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import UniqueConstraint, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
    equipment_model_components,
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


def make_component(
    catalog_release_id: UUID, **overrides: object
) -> ComponentRecord:
    values = {
        "catalog_release_id": catalog_release_id,
        "code": "FLT-F12",
        "name": "Air Filter F-12",
    }
    values.update(overrides)
    return ComponentRecord(**values)


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


def make_inventory_item(
    workspace_id: UUID,
    facility_id: UUID,
    component_id: UUID,
    **overrides: object,
) -> InventoryItemRecord:
    values = {
        "workspace_id": workspace_id,
        "facility_id": facility_id,
        "component_id": component_id,
        "quantity_on_hand": 3,
        "reorder_point": 2,
    }
    values.update(overrides)
    return InventoryItemRecord(**values)


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


def test_component_uses_release_scoped_uniqueness() -> None:
    constraints = [
        constraint
        for constraint in ComponentRecord.__table__.constraints
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


def test_model_component_compatibility_requires_a_shared_release() -> None:
    association_table = equipment_model_components

    assert association_table.primary_key.columns.keys() == [
        "equipment_model_id",
        "component_id",
    ]
    assert {
        tuple(constraint.column_keys)
        for constraint in association_table.foreign_key_constraints
    } == {
        ("catalog_release_id", "equipment_model_id"),
        ("catalog_release_id", "component_id"),
    }


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


def test_inventory_item_uses_workspace_scoped_facility_relationship() -> None:
    item_table = InventoryItemRecord.__table__

    assert item_table.c.workspace_id.nullable is False
    assert item_table.c.facility_id.nullable is False
    assert item_table.c.component_id.nullable is False
    assert any(
        {column.name for column in constraint.columns}
        == {"workspace_id", "facility_id"}
        for constraint in item_table.foreign_key_constraints
    )
    assert any(
        tuple(constraint.columns.keys())
        == ("workspace_id", "facility_id", "component_id")
        for constraint in item_table.constraints
        if isinstance(constraint, UniqueConstraint)
    )


def test_catalog_and_workspace_relationships_are_registered() -> None:
    assert CatalogReleaseRecord.__mapper__.relationships["equipment_models"].mapper.class_ is EquipmentModelRecord
    assert CatalogReleaseRecord.__mapper__.relationships["components"].mapper.class_ is ComponentRecord
    assert EquipmentModelRecord.__mapper__.relationships["components"].mapper.class_ is ComponentRecord
    assert ComponentRecord.__mapper__.relationships["equipment_models"].mapper.class_ is EquipmentModelRecord
    assert ComponentRecord.__mapper__.relationships["inventory_items"].mapper.class_ is InventoryItemRecord
    assert EquipmentModelRecord.__mapper__.relationships["equipment_units"].mapper.class_ is EquipmentUnitRecord
    assert FacilityRecord.__mapper__.relationships["equipment_units"].mapper.class_ is EquipmentUnitRecord
    assert FacilityRecord.__mapper__.relationships["inventory_items"].mapper.class_ is InventoryItemRecord
    assert WorkspaceRecord.__mapper__.relationships["equipment_units"].mapper.class_ is EquipmentUnitRecord
    assert WorkspaceRecord.__mapper__.relationships["inventory_items"].mapper.class_ is InventoryItemRecord


@pytest.mark.integration
def test_catalog_and_equipment_records_generate_ids_and_timestamps(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    integration_session.add(release)
    integration_session.flush()
    model = make_equipment_model(release.id)
    component = make_component(release.id)
    integration_session.add_all([model, component])
    workspace = WorkspaceRecord()
    integration_session.add(workspace)
    integration_session.flush()
    facility = make_facility(workspace.id)
    integration_session.add(facility)
    integration_session.flush()
    unit = make_equipment_unit(workspace.id, facility.id, model.id)
    item = make_inventory_item(workspace.id, facility.id, component.id)
    integration_session.add_all([unit, item])
    integration_session.flush()
    integration_session.refresh(unit)

    assert isinstance(release.id, UUID)
    assert isinstance(release.created_at, datetime)
    assert isinstance(model.id, UUID)
    assert isinstance(model.created_at, datetime)
    assert isinstance(component.id, UUID)
    assert isinstance(component.created_at, datetime)
    assert isinstance(unit.id, UUID)
    assert isinstance(unit.created_at, datetime)
    assert isinstance(unit.updated_at, datetime)
    assert isinstance(item.id, UUID)
    assert isinstance(item.created_at, datetime)
    assert isinstance(item.updated_at, datetime)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("record_factory", "field_name", "invalid_value"),
    [
        (make_catalog_release, "code", " "),
        (make_equipment_model, "code", " "),
        (make_equipment_model, "name", ""),
        (make_component, "code", " "),
        (make_component, "name", ""),
        (make_inventory_item, "quantity_on_hand", -1),
        (make_inventory_item, "reorder_point", -1),
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
    elif record_factory is make_component:
        record = make_component(release.id, **{field_name: invalid_value})
    elif record_factory is make_inventory_item:
        component = make_component(release.id)
        integration_session.add(component)
        integration_session.flush()
        record = make_inventory_item(
            workspace.id, facility.id, component.id, **{field_name: invalid_value}
        )
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
def test_component_code_is_unique_within_one_catalog_release(
    integration_session: Session,
) -> None:
    first_release = make_catalog_release(code="catalog-1")
    second_release = make_catalog_release(code="catalog-2")
    integration_session.add_all([first_release, second_release])
    integration_session.flush()
    integration_session.add_all(
        [
            make_component(first_release.id, code="FLT-F12"),
            make_component(second_release.id, code="FLT-F12"),
        ]
    )
    integration_session.flush()
    integration_session.add(make_component(first_release.id, code="FLT-F12"))

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_model_component_compatibility_rejects_mixed_catalog_releases(
    integration_session: Session,
) -> None:
    first_release = make_catalog_release(code="catalog-1")
    second_release = make_catalog_release(code="catalog-2")
    integration_session.add_all([first_release, second_release])
    integration_session.flush()
    model = make_equipment_model(first_release.id)
    component = make_component(second_release.id)
    integration_session.add_all([model, component])
    integration_session.flush()
    with pytest.raises(IntegrityError):
        integration_session.execute(
            equipment_model_components.insert().values(
                catalog_release_id=first_release.id,
                equipment_model_id=model.id,
                component_id=component.id,
            )
        )


@pytest.mark.integration
def test_model_component_compatibility_rejects_duplicate_pairs(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    integration_session.add(release)
    integration_session.flush()
    model = make_equipment_model(release.id)
    component = make_component(release.id)
    integration_session.add_all([model, component])
    integration_session.flush()
    values = {
        "catalog_release_id": release.id,
        "equipment_model_id": model.id,
        "component_id": component.id,
    }
    integration_session.execute(equipment_model_components.insert().values(**values))
    integration_session.flush()
    with pytest.raises(IntegrityError):
        integration_session.execute(equipment_model_components.insert().values(**values))


@pytest.mark.integration
def test_inventory_item_rejects_facility_from_another_workspace(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    first_workspace = WorkspaceRecord()
    second_workspace = WorkspaceRecord()
    integration_session.add_all([release, first_workspace, second_workspace])
    integration_session.flush()
    component = make_component(release.id)
    facility = make_facility(second_workspace.id)
    integration_session.add_all([component, facility])
    integration_session.flush()
    integration_session.add(
        make_inventory_item(first_workspace.id, facility.id, component.id)
    )

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_inventory_item_is_unique_per_workspace_facility_and_component(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    first_workspace = WorkspaceRecord()
    second_workspace = WorkspaceRecord()
    integration_session.add_all([release, first_workspace, second_workspace])
    integration_session.flush()
    component = make_component(release.id)
    first_facility = make_facility(first_workspace.id)
    second_facility = make_facility(second_workspace.id)
    integration_session.add_all([component, first_facility, second_facility])
    integration_session.flush()
    integration_session.add_all(
        [
            make_inventory_item(first_workspace.id, first_facility.id, component.id),
            make_inventory_item(second_workspace.id, second_facility.id, component.id),
        ]
    )
    integration_session.flush()
    integration_session.add(
        make_inventory_item(first_workspace.id, first_facility.id, component.id)
    )

    with pytest.raises(IntegrityError):
        integration_session.flush()


@pytest.mark.integration
def test_component_delete_is_restricted_when_compatibility_exists(
    integration_session: Session,
) -> None:
    release = make_catalog_release()
    integration_session.add(release)
    integration_session.flush()
    model = make_equipment_model(release.id)
    component = make_component(release.id)
    integration_session.add_all([model, component])
    integration_session.flush()
    integration_session.execute(
        equipment_model_components.insert().values(
            catalog_release_id=release.id,
            equipment_model_id=model.id,
            component_id=component.id,
        )
    )
    integration_session.flush()

    with pytest.raises(IntegrityError):
        integration_session.execute(
            delete(ComponentRecord).where(ComponentRecord.id == component.id)
        )


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
