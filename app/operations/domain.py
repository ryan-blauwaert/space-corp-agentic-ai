"""Typed domain records and lifecycle validation for operational incidents."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


INCIDENT_REFERENCE_CODE_MAX_LENGTH = 64
WORK_ORDER_REFERENCE_CODE_MAX_LENGTH = 64


INCIDENT_FAULT_CODE_MAX_LENGTH = 64


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


class WorkOrderPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkOrderStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


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
class NewWorkOrder:
    facility_id: UUID
    originating_incident_id: UUID | None
    target_equipment_unit_id: UUID | None
    reference_code: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    due_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_required_text("Work order reference code", self.reference_code, WORK_ORDER_REFERENCE_CODE_MAX_LENGTH)
        _validate_work_order_lifecycle(self.priority, self.status, self.due_at, self.completed_at)


@dataclass(frozen=True, slots=True)
class WorkOrder:
    id: UUID
    workspace_id: UUID
    facility_id: UUID
    originating_incident_id: UUID | None
    target_equipment_unit_id: UUID | None
    reference_code: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_required_text("Work order reference code", self.reference_code, WORK_ORDER_REFERENCE_CODE_MAX_LENGTH)
        _validate_work_order_lifecycle(self.priority, self.status, self.due_at, self.completed_at, created_at=self.created_at)


def _validate_required_text(field_name: str, value: str, maximum_length: int) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")
    if len(value) > maximum_length:
        raise ValueError(f"{field_name} must be at most {maximum_length} characters.")


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


def _validate_work_order_lifecycle(
    priority: WorkOrderPriority, status: WorkOrderStatus, due_at: datetime | None,
    completed_at: datetime | None, *, created_at: datetime | None = None,
) -> None:
    if not isinstance(priority, WorkOrderPriority):
        raise ValueError("Work order priority must be a WorkOrderPriority.")
    if not isinstance(status, WorkOrderStatus):
        raise ValueError("Work order status must be a WorkOrderStatus.")
    if due_at is not None:
        _validate_timezone_aware("Work order due time", due_at)
    if status is WorkOrderStatus.COMPLETED and completed_at is None:
        raise ValueError("Completed work orders must include a completion time.")
    if status is not WorkOrderStatus.COMPLETED and completed_at is not None:
        raise ValueError("Only completed work orders may include a completion time.")
    if completed_at is not None:
        _validate_timezone_aware("Work order completion time", completed_at)
        if created_at is not None:
            _validate_timezone_aware("Work order creation time", created_at)
            if completed_at < created_at:
                raise ValueError("Work order completion time cannot precede creation time.")


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
