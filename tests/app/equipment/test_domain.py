from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.equipment.domain import (
    CATALOG_RELEASE_CODE_MAX_LENGTH,
    COMPONENT_CODE_MAX_LENGTH,
    COMPONENT_NAME_MAX_LENGTH,
    EQUIPMENT_MODEL_CODE_MAX_LENGTH,
    EQUIPMENT_MODEL_NAME_MAX_LENGTH,
    EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH,
    INCIDENT_FAULT_CODE_MAX_LENGTH,
    INCIDENT_REFERENCE_CODE_MAX_LENGTH,
    CatalogRelease,
    Component,
    EquipmentModel,
    EquipmentOperationalStatus,
    EquipmentUnit,
    InventoryItem,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    NewCatalogRelease,
    NewComponent,
    NewEquipmentModel,
    NewEquipmentUnit,
    NewInventoryItem,
    NewIncident,
)


def test_catalog_release_accepts_valid_data() -> None:
    created_at = datetime.now(UTC)
    release = CatalogRelease(id=uuid4(), code="catalog-1", created_at=created_at)

    assert release.code == "catalog-1"
    assert release.created_at is created_at


@pytest.mark.parametrize(
    ("code", "message"),
    [("", "must not be blank"), (" " * 65, "must not be blank"), ("x" * 65, "at most")],
)
def test_new_catalog_release_rejects_invalid_code(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        NewCatalogRelease(code=code)


def test_equipment_model_accepts_valid_data() -> None:
    model = EquipmentModel(
        id=uuid4(),
        catalog_release_id=uuid4(),
        code="ECS-4",
        name="Environmental Control System 4",
        created_at=datetime.now(UTC),
    )

    assert model.code == "ECS-4"


def test_component_accepts_valid_data() -> None:
    component = Component(
        id=uuid4(),
        catalog_release_id=uuid4(),
        code="FLT-F12",
        name="Air Filter F-12",
        created_at=datetime.now(UTC),
    )

    assert component.code == "FLT-F12"


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("code", "", "must not be blank"),
        ("code", "x" * (COMPONENT_CODE_MAX_LENGTH + 1), "at most"),
        ("name", "\t", "must not be blank"),
        ("name", "x" * (COMPONENT_NAME_MAX_LENGTH + 1), "at most"),
    ],
)
def test_new_component_rejects_invalid_text(
    field_name: str, value: str, message: str
) -> None:
    values: dict[str, object] = {
        "catalog_release_id": uuid4(),
        "code": "FLT-F12",
        "name": "Air Filter F-12",
    }
    values[field_name] = value

    with pytest.raises(ValueError, match=message):
        NewComponent(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("code", "", "must not be blank"),
        ("code", "x" * (EQUIPMENT_MODEL_CODE_MAX_LENGTH + 1), "at most"),
        ("name", "\t", "must not be blank"),
        ("name", "x" * (EQUIPMENT_MODEL_NAME_MAX_LENGTH + 1), "at most"),
    ],
)
def test_new_equipment_model_rejects_invalid_text(
    field_name: str, value: str, message: str
) -> None:
    values: dict[str, object] = {
        "catalog_release_id": uuid4(),
        "code": "ECS-4",
        "name": "Environmental Control System 4",
    }
    values[field_name] = value

    with pytest.raises(ValueError, match=message):
        NewEquipmentModel(**values)  # type: ignore[arg-type]


def test_equipment_unit_accepts_valid_data() -> None:
    unit = EquipmentUnit(
        id=uuid4(),
        workspace_id=uuid4(),
        facility_id=uuid4(),
        equipment_model_id=uuid4(),
        asset_tag="ECS-14",
        operational_status=EquipmentOperationalStatus.DEGRADED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert unit.operational_status is EquipmentOperationalStatus.DEGRADED


def test_inventory_item_accepts_valid_data() -> None:
    item = InventoryItem(
        id=uuid4(),
        workspace_id=uuid4(),
        facility_id=uuid4(),
        component_id=uuid4(),
        quantity_on_hand=0,
        reorder_point=2,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert item.quantity_on_hand == 0


@pytest.mark.parametrize(
    ("quantity_on_hand", "reorder_point", "message"),
    [
        (-1, 0, "Quantity on hand must not be negative"),
        (0, -1, "Reorder point must not be negative"),
        (True, 0, "Quantity on hand must be a whole number"),
        (0, 1.5, "Reorder point must be a whole number"),
    ],
)
def test_new_inventory_item_rejects_invalid_stock_levels(
    quantity_on_hand: object, reorder_point: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        NewInventoryItem(
            facility_id=uuid4(),
            component_id=uuid4(),
            quantity_on_hand=quantity_on_hand,  # type: ignore[arg-type]
            reorder_point=reorder_point,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("asset_tag", "status", "message"),
    [
        ("", EquipmentOperationalStatus.OPERATIONAL, "must not be blank"),
        ("x" * (EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH + 1), EquipmentOperationalStatus.OPERATIONAL, "at most"),
        ("ECS-14", "operational", "must be an EquipmentOperationalStatus"),
    ],
)
def test_new_equipment_unit_rejects_invalid_data(
    asset_tag: str, status: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        NewEquipmentUnit(
            facility_id=uuid4(),
            equipment_model_id=uuid4(),
            asset_tag=asset_tag,
            operational_status=status,  # type: ignore[arg-type]
        )


def test_domain_models_are_immutable() -> None:
    release = NewCatalogRelease(code="catalog-1")
    component = NewComponent(
        catalog_release_id=uuid4(),
        code="FLT-F12",
        name="Air Filter F-12",
    )

    with pytest.raises(AttributeError):
        release.code = "catalog-2"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        component.name = "Replacement Filter F-12"  # type: ignore[misc]


def test_catalog_release_length_constant_matches_contract() -> None:
    assert CATALOG_RELEASE_CODE_MAX_LENGTH == 64


def test_incident_normalizes_fault_code_and_accepts_valid_lifecycle() -> None:
    occurred_at = datetime.now(UTC)
    incident = NewIncident(
        facility_id=uuid4(),
        equipment_unit_id=uuid4(),
        reference_code="INC-ECS-001",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        occurred_at=occurred_at,
        fault_code=" airflow_low ",
    )

    assert incident.fault_code == "AIRFLOW_LOW"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"reference_code": ""}, "must not be blank"),
        ({"reference_code": "x" * (INCIDENT_REFERENCE_CODE_MAX_LENGTH + 1)}, "at most"),
        ({"fault_code": "x" * (INCIDENT_FAULT_CODE_MAX_LENGTH + 1)}, "at most"),
        ({"status": IncidentStatus.RESOLVED}, "must include a resolution time"),
        ({"resolved_at": datetime.now(UTC)}, "may include a resolution time"),
        ({"occurred_at": datetime.now()}, "timezone-aware"),
    ],
)
def test_new_incident_rejects_invalid_data(
    overrides: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "facility_id": uuid4(),
        "equipment_unit_id": uuid4(),
        "reference_code": "INC-ECS-001",
        "severity": IncidentSeverity.HIGH,
        "status": IncidentStatus.OPEN,
        "occurred_at": datetime.now(UTC),
        "fault_code": "AIRFLOW_LOW",
        "resolved_at": None,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        NewIncident(**values)  # type: ignore[arg-type]


def test_incident_requires_normalized_persisted_fault_code() -> None:
    with pytest.raises(ValueError, match="trimmed and uppercase"):
        Incident(
            id=uuid4(), workspace_id=uuid4(), facility_id=uuid4(), equipment_unit_id=None,
            reference_code="INC-LUN-001", severity=IncidentSeverity.LOW,
            status=IncidentStatus.OPEN, occurred_at=datetime.now(UTC),
            fault_code="airflow_low", resolved_at=None,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
