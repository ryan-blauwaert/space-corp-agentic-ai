"""Typed public read responses and bounded query parameters."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.pagination import PaginationMetadata, PaginationQuery
from app.operations.domain import IncidentSeverity, IncidentStatus, WorkOrderPriority, WorkOrderStatus


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    pagination: PaginationMetadata


class WorkOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    facility_id: UUID
    originating_incident_id: UUID | None = Field(description="Incident that initiated this work; its affected unit may differ from the work target.")
    target_equipment_unit_id: UUID | None = Field(description="Unit targeted by the work, independently of the originating incident; null permits facility-level work.")
    reference_code: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkOrderListResponse(BaseModel):
    items: list[WorkOrderResponse]
    pagination: PaginationMetadata


class IncidentQuery(PaginationQuery):
    facility_id: UUID | None = None
    equipment_unit_id: UUID | None = None
    status: IncidentStatus | None = None
    fault_code: str | None = Field(default=None, min_length=1, max_length=64, description="Exact fault classification, trimmed and uppercased; unclassified incidents do not match.")
    occurred_from: AwareDatetime | None = Field(default=None, description="Inclusive occurrence-time lower bound; timezone required.")
    occurred_before: AwareDatetime | None = Field(default=None, description="Exclusive occurrence-time upper bound; timezone required, later than occurred_from when both are supplied.")

    @field_validator("fault_code", mode="before")
    @classmethod
    def normalize_fault_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if (self.occurred_from is not None and self.occurred_before is not None
                and self.occurred_from >= self.occurred_before):
            raise ValueError("occurred_from must be earlier than occurred_before")
        return self


class WorkOrderQuery(PaginationQuery):
    facility_id: UUID | None = None
    status: WorkOrderStatus | None = None
    priority: WorkOrderPriority | None = None
