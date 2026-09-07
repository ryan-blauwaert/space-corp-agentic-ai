from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


FACILITY_CODE_MAX_LENGTH = 64
FACILITY_NAME_MAX_LENGTH = 256
FACILITY_LOCATION_MAX_LENGTH = 256


class FacilityType(StrEnum):
    LUNAR_INSTALLATION = "lunar_installation"
    ORBITAL_STATION = "orbital_station"
    LOGISTICS_DEPOT = "logistics_depot"
    MISSION_CONTROL_CENTER = "mission_control_center"


class FacilityOperationalStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class NewFacility:
    """Validated Facility data before it is assigned persistence identifiers."""

    code: str
    name: str
    facility_type: FacilityType
    location: str
    operational_status: FacilityOperationalStatus

    def __post_init__(self) -> None:
        _validate_required_text(self.code, self.name, self.location)
        _validate_enum_values(self.facility_type, self.operational_status)


@dataclass(frozen=True, slots=True)
class Facility:
    """A workspace-owned operational facility."""

    id: UUID
    workspace_id: UUID
    code: str
    name: str
    facility_type: FacilityType
    location: str
    operational_status: FacilityOperationalStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_required_text(self.code, self.name, self.location)
        _validate_enum_values(self.facility_type, self.operational_status)


def _validate_required_text(code: str, name: str, location: str) -> None:
    for field_name, value, maximum_length in (
        ("code", code, FACILITY_CODE_MAX_LENGTH),
        ("name", name, FACILITY_NAME_MAX_LENGTH),
        ("location", location, FACILITY_LOCATION_MAX_LENGTH),
    ):
        if not value.strip():
            raise ValueError(f"Facility {field_name} must not be blank.")
        if len(value) > maximum_length:
            raise ValueError(
                f"Facility {field_name} must be at most {maximum_length} characters."
            )


def _validate_enum_values(
    facility_type: FacilityType,
    operational_status: FacilityOperationalStatus,
) -> None:
    for field_name, value, expected_type in (
        ("facility_type", facility_type, FacilityType),
        ("operational_status", operational_status, FacilityOperationalStatus),
    ):
        if not isinstance(value, expected_type):
            raise ValueError(f"Facility {field_name} must be a {expected_type.__name__}.")
