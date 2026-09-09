from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.equipment.domain import (
    CATALOG_RELEASE_CODE_MAX_LENGTH,
    EQUIPMENT_MODEL_CODE_MAX_LENGTH,
    EQUIPMENT_MODEL_NAME_MAX_LENGTH,
    EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH,
    CatalogRelease,
    EquipmentModel,
    EquipmentOperationalStatus,
    EquipmentUnit,
    NewCatalogRelease,
    NewEquipmentModel,
    NewEquipmentUnit,
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

    with pytest.raises(AttributeError):
        release.code = "catalog-2"  # type: ignore[misc]


def test_catalog_release_length_constant_matches_contract() -> None:
    assert CATALOG_RELEASE_CODE_MAX_LENGTH == 64
