"""Repositories for workspace-owned operational incidents."""

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
    _validate_incident_lifecycle,
)
from app.operations.models import IncidentRecord


class IncidentRepository(Protocol):
    """Persistence operations for workspace-owned operational incidents."""

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


class SqlAlchemyIncidentRepository:
    """SQLAlchemy implementation of workspace-scoped incident persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

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
