"""Typed domain records for catalog releases, equipment models, and units."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


CATALOG_RELEASE_CODE_MAX_LENGTH = 64
EQUIPMENT_MODEL_CODE_MAX_LENGTH = 64
EQUIPMENT_MODEL_NAME_MAX_LENGTH = 256
EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH = 64


class EquipmentOperationalStatus(StrEnum):
    """The current condition of an individually deployed equipment unit."""

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True, slots=True)
class NewCatalogRelease:
    """Validated shared catalog-release data before persistence identifiers exist."""

    code: str

    def __post_init__(self) -> None:
        _validate_required_text(
            "Catalog release code", self.code, CATALOG_RELEASE_CODE_MAX_LENGTH
        )


@dataclass(frozen=True, slots=True)
class CatalogRelease:
    """A stable shared identity for one equipment and component catalog release."""

    id: UUID
    code: str
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_required_text(
            "Catalog release code", self.code, CATALOG_RELEASE_CODE_MAX_LENGTH
        )


@dataclass(frozen=True, slots=True)
class NewEquipmentModel:
    """Validated shared equipment-model data before persistence identifiers exist."""

    catalog_release_id: UUID
    code: str
    name: str

    def __post_init__(self) -> None:
        _validate_required_text(
            "Equipment model code", self.code, EQUIPMENT_MODEL_CODE_MAX_LENGTH
        )
        _validate_required_text(
            "Equipment model name", self.name, EQUIPMENT_MODEL_NAME_MAX_LENGTH
        )


@dataclass(frozen=True, slots=True)
class EquipmentModel:
    """An immutable shared equipment-model revision in one catalog release."""

    id: UUID
    catalog_release_id: UUID
    code: str
    name: str
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_required_text(
            "Equipment model code", self.code, EQUIPMENT_MODEL_CODE_MAX_LENGTH
        )
        _validate_required_text(
            "Equipment model name", self.name, EQUIPMENT_MODEL_NAME_MAX_LENGTH
        )


@dataclass(frozen=True, slots=True)
class NewEquipmentUnit:
    """Validated deployed-unit data before persistence identifiers exist."""

    facility_id: UUID
    equipment_model_id: UUID
    asset_tag: str
    operational_status: EquipmentOperationalStatus

    def __post_init__(self) -> None:
        _validate_required_text(
            "Equipment unit asset tag",
            self.asset_tag,
            EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH,
        )
        if not isinstance(self.operational_status, EquipmentOperationalStatus):
            raise ValueError(
                "Equipment unit operational status must be an "
                "EquipmentOperationalStatus."
            )


@dataclass(frozen=True, slots=True)
class EquipmentUnit:
    """A workspace-owned instance of an equipment model deployed at a Facility."""

    id: UUID
    workspace_id: UUID
    facility_id: UUID
    equipment_model_id: UUID
    asset_tag: str
    operational_status: EquipmentOperationalStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_required_text(
            "Equipment unit asset tag",
            self.asset_tag,
            EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH,
        )
        if not isinstance(self.operational_status, EquipmentOperationalStatus):
            raise ValueError(
                "Equipment unit operational status must be an "
                "EquipmentOperationalStatus."
            )


def _validate_required_text(field_name: str, value: str, maximum_length: int) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")
    if len(value) > maximum_length:
        raise ValueError(f"{field_name} must be at most {maximum_length} characters.")
