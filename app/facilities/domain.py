from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


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


def _validate_required_text(code: str, name: str, location: str) -> None:
    for field_name, value in {
        "code": code,
        "name": name,
        "location": location,
    }.items():
        if not value.strip():
            raise ValueError(f"Facility {field_name} must not be blank.")
