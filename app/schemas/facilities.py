"""HTTP response schemas for Facility API operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.facilities.domain import FacilityOperationalStatus, FacilityType
from app.schemas.pagination import PaginationMetadata


class FacilityResponse(BaseModel):
    """Public representation of a Facility record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    facility_type: FacilityType
    body_or_system: str | None = Field(
        default=None,
        max_length=128,
        description="Stored celestial body or system context, e.g. Earth’s Moon or Earth–Moon system. Null means unspecified; not inferred from facility type.",
    )
    location: str
    operational_status: FacilityOperationalStatus
    created_at: datetime
    updated_at: datetime


class FacilityListResponse(BaseModel):
    """A page of Facilities and its pagination metadata."""

    items: list[FacilityResponse]
    pagination: PaginationMetadata
