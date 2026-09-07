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
        for field_name in ("code", "name", "location"):
            value = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"Facility {field_name} must not be blank.")
