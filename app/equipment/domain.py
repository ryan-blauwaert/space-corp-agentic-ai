"""Typed domain records for the equipment catalog and deployed units."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


CATALOG_RELEASE_CODE_MAX_LENGTH = 64
EQUIPMENT_MODEL_CODE_MAX_LENGTH = 64
EQUIPMENT_MODEL_NAME_MAX_LENGTH = 256
COMPONENT_CODE_MAX_LENGTH = 64
COMPONENT_NAME_MAX_LENGTH = 256
EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH = 64
INCIDENT_REFERENCE_CODE_MAX_LENGTH = 64
INCIDENT_FAULT_CODE_MAX_LENGTH = 64


class EquipmentOperationalStatus(StrEnum):
    """The current condition of an individually deployed equipment unit."""

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class IncidentSeverity(StrEnum):
    """The operational impact assigned to an incident."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    """The current lifecycle state of an incident."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


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
class NewComponent:
    """Validated shared component data before persistence identifiers exist."""

    catalog_release_id: UUID
    code: str
    name: str

    def __post_init__(self) -> None:
        _validate_required_text("Component code", self.code, COMPONENT_CODE_MAX_LENGTH)
        _validate_required_text("Component name", self.name, COMPONENT_NAME_MAX_LENGTH)


@dataclass(frozen=True, slots=True)
class Component:
    """An immutable shared component revision in one catalog release."""

    id: UUID
    catalog_release_id: UUID
    code: str
    name: str
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_required_text("Component code", self.code, COMPONENT_CODE_MAX_LENGTH)
        _validate_required_text("Component name", self.name, COMPONENT_NAME_MAX_LENGTH)


@dataclass(frozen=True, slots=True)
class NewInventoryItem:
    """Validated local component stock data before persistence identifiers exist."""

    facility_id: UUID
    component_id: UUID
    quantity_on_hand: int
    reorder_point: int

    def __post_init__(self) -> None:
        _validate_nonnegative_whole_number("Quantity on hand", self.quantity_on_hand)
        _validate_nonnegative_whole_number("Reorder point", self.reorder_point)


@dataclass(frozen=True, slots=True)
class InventoryItem:
    """A workspace-owned quantity of one component at one Facility."""

    id: UUID
    workspace_id: UUID
    facility_id: UUID
    component_id: UUID
    quantity_on_hand: int
    reorder_point: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_nonnegative_whole_number("Quantity on hand", self.quantity_on_hand)
        _validate_nonnegative_whole_number("Reorder point", self.reorder_point)


@dataclass(frozen=True, slots=True)
class NewIncident:
    """Validated incident data before persistence identifiers exist."""

    facility_id: UUID
    equipment_unit_id: UUID | None
    reference_code: str
    severity: IncidentSeverity
    status: IncidentStatus
    occurred_at: datetime
    fault_code: str | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_required_text(
            "Incident reference code",
            self.reference_code,
            INCIDENT_REFERENCE_CODE_MAX_LENGTH,
        )
        _validate_incident_lifecycle(
            self.severity,
            self.status,
            self.occurred_at,
            self.resolved_at,
        )
        object.__setattr__(self, "fault_code", _normalize_fault_code(self.fault_code))


@dataclass(frozen=True, slots=True)
class Incident:
    """A workspace-owned operational event at a Facility."""

    id: UUID
    workspace_id: UUID
    facility_id: UUID
    equipment_unit_id: UUID | None
    reference_code: str
    severity: IncidentSeverity
    status: IncidentStatus
    occurred_at: datetime
    fault_code: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_required_text(
            "Incident reference code",
            self.reference_code,
            INCIDENT_REFERENCE_CODE_MAX_LENGTH,
        )
        _validate_incident_lifecycle(
            self.severity,
            self.status,
            self.occurred_at,
            self.resolved_at,
        )
        normalized_fault_code = _normalize_fault_code(self.fault_code)
        if self.fault_code != normalized_fault_code:
            raise ValueError("Incident fault code must be trimmed and uppercase.")


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


def _validate_nonnegative_whole_number(field_name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a whole number.")
    if value < 0:
        raise ValueError(f"{field_name} must not be negative.")


def _validate_incident_lifecycle(
    severity: IncidentSeverity,
    status: IncidentStatus,
    occurred_at: datetime,
    resolved_at: datetime | None,
) -> None:
    if not isinstance(severity, IncidentSeverity):
        raise ValueError("Incident severity must be an IncidentSeverity.")
    if not isinstance(status, IncidentStatus):
        raise ValueError("Incident status must be an IncidentStatus.")
    _validate_timezone_aware("Incident occurrence time", occurred_at)
    if status is IncidentStatus.RESOLVED and resolved_at is None:
        raise ValueError("Resolved incidents must include a resolution time.")
    if status is not IncidentStatus.RESOLVED and resolved_at is not None:
        raise ValueError("Only resolved incidents may include a resolution time.")
    if resolved_at is not None:
        _validate_timezone_aware("Incident resolution time", resolved_at)
        if resolved_at < occurred_at:
            raise ValueError("Incident resolution time cannot precede occurrence time.")


def _normalize_fault_code(fault_code: str | None) -> str | None:
    if fault_code is None:
        return None

    normalized = fault_code.strip().upper()
    _validate_required_text(
        "Incident fault code", normalized, INCIDENT_FAULT_CODE_MAX_LENGTH
    )
    return normalized


def _validate_timezone_aware(field_name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
