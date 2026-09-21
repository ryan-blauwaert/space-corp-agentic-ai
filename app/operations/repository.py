"""Repositories for workspace-owned operational records."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.operations.domain import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    NewIncident,
    NewWorkOrder,
    WorkOrder,
    WorkOrderPriority,
    WorkOrderStatus,
    _validate_incident_lifecycle,
    _validate_work_order_lifecycle,
)
from app.operations.models import IncidentRecord, WorkOrderRecord


class IncidentRepository(Protocol):
    """Persistence operations for workspace-owned operational incidents."""

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        equipment_unit_id: UUID | None = None,
        status: IncidentStatus | None = None,
        fault_code: str | None = None,
        occurred_from: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> tuple[list[Incident], int]:
        """Return a filtered workspace page and its total before pagination."""

    def create(self, workspace_id: UUID, incident: NewIncident) -> Incident:
        """Create an incident owned by the supplied workspace."""

    def get_by_id(self, workspace_id: UUID, incident_id: UUID) -> Incident | None:
        """Return an incident only when it belongs to the supplied workspace."""

    def list_by_facility(
        self,
        workspace_id: UUID,
        facility_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Incident]:
        """Return one page of incidents at a workspace Facility."""

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        """Return the number of incidents at a workspace Facility."""

    def update_lifecycle(
        self,
        workspace_id: UUID,
        incident_id: UUID,
        *,
        severity: IncidentSeverity,
        status: IncidentStatus,
        resolved_at: datetime | None,
    ) -> Incident | None:
        """Update only the mutable lifecycle fields of an incident."""


class WorkOrderRepository(Protocol):
    """Persistence operations for workspace-owned maintenance work."""

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        status: WorkOrderStatus | None = None,
        priority: WorkOrderPriority | None = None,
    ) -> tuple[list[WorkOrder], int]:
        """Return a filtered workspace page and its total before pagination."""

    def create(self, workspace_id: UUID, work_order: NewWorkOrder) -> WorkOrder:
        """Create a work order owned by the supplied workspace."""

    def get_by_id(self, workspace_id: UUID, work_order_id: UUID) -> WorkOrder | None:
        """Return a work order only when it belongs to the supplied workspace."""

    def list_by_facility(
        self, workspace_id: UUID, facility_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[WorkOrder]:
        """Return one page of work orders at a workspace Facility."""

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        """Return the number of work orders at a workspace Facility."""

    def update_lifecycle(
        self,
        workspace_id: UUID,
        work_order_id: UUID,
        *,
        priority: WorkOrderPriority,
        status: WorkOrderStatus,
        due_at: datetime | None,
        completed_at: datetime | None,
    ) -> WorkOrder | None:
        """Update only the mutable lifecycle fields of a work order."""


class SqlAlchemyIncidentRepository:
    """SQLAlchemy implementation of workspace-scoped incident persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        equipment_unit_id: UUID | None = None,
        status: IncidentStatus | None = None,
        fault_code: str | None = None,
        occurred_from: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> tuple[list[Incident], int]:
        statement = select(IncidentRecord).where(IncidentRecord.workspace_id == workspace_id)
        if facility_id is not None:
            statement = statement.where(IncidentRecord.facility_id == facility_id)
        if equipment_unit_id is not None:
            statement = statement.where(IncidentRecord.equipment_unit_id == equipment_unit_id)
        if status is not None:
            statement = statement.where(IncidentRecord.status == status)
        if fault_code is not None:
            statement = statement.where(IncidentRecord.fault_code == fault_code)
        if occurred_from is not None:
            statement = statement.where(IncidentRecord.occurred_at >= occurred_from)
        if occurred_before is not None:
            statement = statement.where(IncidentRecord.occurred_at < occurred_before)
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        records = self._session.scalars(
            statement.order_by(IncidentRecord.occurred_at, IncidentRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return [_incident_to_domain(record) for record in records], total

    def create(self, workspace_id: UUID, incident: NewIncident) -> Incident:
        record = IncidentRecord(
            workspace_id=workspace_id,
            facility_id=incident.facility_id,
            equipment_unit_id=incident.equipment_unit_id,
            reference_code=incident.reference_code,
            severity=incident.severity.value,
            status=incident.status.value,
            occurred_at=incident.occurred_at,
            fault_code=incident.fault_code,
            resolved_at=incident.resolved_at,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return _incident_to_domain(record)

    def get_by_id(self, workspace_id: UUID, incident_id: UUID) -> Incident | None:
        record = self._session.scalar(
            select(IncidentRecord).where(
                IncidentRecord.workspace_id == workspace_id,
                IncidentRecord.id == incident_id,
            )
        )
        return None if record is None else _incident_to_domain(record)

    def list_by_facility(
        self,
        workspace_id: UUID,
        facility_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Incident]:
        statement = (
            select(IncidentRecord)
            .where(
                IncidentRecord.workspace_id == workspace_id,
                IncidentRecord.facility_id == facility_id,
            )
            .order_by(IncidentRecord.occurred_at, IncidentRecord.reference_code)
            .limit(limit)
            .offset(offset)
        )
        return [_incident_to_domain(record) for record in self._session.scalars(statement)]

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        statement = select(func.count()).where(
            IncidentRecord.workspace_id == workspace_id,
            IncidentRecord.facility_id == facility_id,
        )
        return self._session.scalar(statement) or 0

    def update_lifecycle(
        self,
        workspace_id: UUID,
        incident_id: UUID,
        *,
        severity: IncidentSeverity,
        status: IncidentStatus,
        resolved_at: datetime | None,
    ) -> Incident | None:
        record = self._session.scalar(
            select(IncidentRecord).where(
                IncidentRecord.workspace_id == workspace_id,
                IncidentRecord.id == incident_id,
            )
        )
        if record is None:
            return None

        _validate_incident_lifecycle(
            severity,
            status,
            record.occurred_at,
            resolved_at,
        )
        record.severity = severity.value
        record.status = status.value
        record.resolved_at = resolved_at
        self._session.flush()
        self._session.refresh(record)
        return _incident_to_domain(record)


class SqlAlchemyWorkOrderRepository:
    """SQLAlchemy implementation of workspace-scoped work-order persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        status: WorkOrderStatus | None = None,
        priority: WorkOrderPriority | None = None,
    ) -> tuple[list[WorkOrder], int]:
        statement = select(WorkOrderRecord).where(WorkOrderRecord.workspace_id == workspace_id)
        if facility_id is not None:
            statement = statement.where(WorkOrderRecord.facility_id == facility_id)
        if status is not None:
            statement = statement.where(WorkOrderRecord.status == status)
        if priority is not None:
            statement = statement.where(WorkOrderRecord.priority == priority)
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        records = self._session.scalars(
            statement.order_by(WorkOrderRecord.reference_code, WorkOrderRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return [_work_order_to_domain(record) for record in records], total

    def create(self, workspace_id: UUID, work_order: NewWorkOrder) -> WorkOrder:
        record = WorkOrderRecord(
            workspace_id=workspace_id,
            facility_id=work_order.facility_id,
            originating_incident_id=work_order.originating_incident_id,
            target_equipment_unit_id=work_order.target_equipment_unit_id,
            reference_code=work_order.reference_code,
            priority=work_order.priority.value,
            status=work_order.status.value,
            due_at=work_order.due_at,
            completed_at=work_order.completed_at,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return _work_order_to_domain(record)

    def get_by_id(self, workspace_id: UUID, work_order_id: UUID) -> WorkOrder | None:
        record = self._session.scalar(
            select(WorkOrderRecord).where(
                WorkOrderRecord.workspace_id == workspace_id, WorkOrderRecord.id == work_order_id
            )
        )
        return None if record is None else _work_order_to_domain(record)

    def list_by_facility(
        self, workspace_id: UUID, facility_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[WorkOrder]:
        statement = (
            select(WorkOrderRecord)
            .where(
                WorkOrderRecord.workspace_id == workspace_id,
                WorkOrderRecord.facility_id == facility_id,
            )
            .order_by(WorkOrderRecord.due_at, WorkOrderRecord.reference_code)
            .limit(limit)
            .offset(offset)
        )
        return [_work_order_to_domain(record) for record in self._session.scalars(statement)]

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        return (
            self._session.scalar(
                select(func.count()).where(
                    WorkOrderRecord.workspace_id == workspace_id,
                    WorkOrderRecord.facility_id == facility_id,
                )
            )
            or 0
        )

    def update_lifecycle(
        self,
        workspace_id: UUID,
        work_order_id: UUID,
        *,
        priority: WorkOrderPriority,
        status: WorkOrderStatus,
        due_at: datetime | None,
        completed_at: datetime | None,
    ) -> WorkOrder | None:
        record = self._session.scalar(
            select(WorkOrderRecord).where(
                WorkOrderRecord.workspace_id == workspace_id, WorkOrderRecord.id == work_order_id
            )
        )
        if record is None:
            return None
        _validate_work_order_lifecycle(
            priority, status, due_at, completed_at, created_at=record.created_at
        )
        record.priority, record.status, record.due_at, record.completed_at = (
            priority.value,
            status.value,
            due_at,
            completed_at,
        )
        self._session.flush()
        self._session.refresh(record)
        return _work_order_to_domain(record)


def _incident_to_domain(record: IncidentRecord) -> Incident:
    return Incident(
        id=record.id,
        workspace_id=record.workspace_id,
        facility_id=record.facility_id,
        equipment_unit_id=record.equipment_unit_id,
        reference_code=record.reference_code,
        severity=IncidentSeverity(record.severity),
        status=IncidentStatus(record.status),
        occurred_at=record.occurred_at,
        fault_code=record.fault_code,
        resolved_at=record.resolved_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _work_order_to_domain(record: WorkOrderRecord) -> WorkOrder:
    return WorkOrder(
        id=record.id,
        workspace_id=record.workspace_id,
        facility_id=record.facility_id,
        originating_incident_id=record.originating_incident_id,
        target_equipment_unit_id=record.target_equipment_unit_id,
        reference_code=record.reference_code,
        priority=WorkOrderPriority(record.priority),
        status=WorkOrderStatus(record.status),
        due_at=record.due_at,
        completed_at=record.completed_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
