from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.facilities.domain import Facility, FacilityOperationalStatus, FacilityType, NewFacility
from app.facilities.models import FacilityRecord


class FacilityRepository(Protocol):
    """Persistence operations for workspace-owned Facilities."""

    def create(self, workspace_id: UUID, facility: NewFacility) -> Facility:
        """Create a Facility owned by the supplied workspace."""

    def get_by_id(self, workspace_id: UUID, facility_id: UUID) -> Facility | None:
        """Return a Facility only when it belongs to the supplied workspace."""

    def list_by_workspace(self, workspace_id: UUID) -> list[Facility]:
        """Return all Facilities owned by the supplied workspace."""


class SqlAlchemyFacilityRepository:
    """SQLAlchemy implementation of workspace-scoped Facility persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, workspace_id: UUID, facility: NewFacility) -> Facility:
        record = FacilityRecord(
            workspace_id=workspace_id,
            code=facility.code,
            name=facility.name,
            facility_type=facility.facility_type.value,
            location=facility.location,
            operational_status=facility.operational_status.value,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)

        return _to_domain(record)

    def get_by_id(self, workspace_id: UUID, facility_id: UUID) -> Facility | None:
        statement = select(FacilityRecord).where(
            FacilityRecord.workspace_id == workspace_id,
            FacilityRecord.id == facility_id,
        )
        record = self._session.scalar(statement)

        return None if record is None else _to_domain(record)

    def list_by_workspace(self, workspace_id: UUID) -> list[Facility]:
        statement = (
            select(FacilityRecord)
            .where(FacilityRecord.workspace_id == workspace_id)
            .order_by(FacilityRecord.code)
        )

        return [_to_domain(record) for record in self._session.scalars(statement)]


def _to_domain(record: FacilityRecord) -> Facility:
    return Facility(
        id=record.id,
        workspace_id=record.workspace_id,
        code=record.code,
        name=record.name,
        facility_type=FacilityType(record.facility_type),
        location=record.location,
        operational_status=FacilityOperationalStatus(record.operational_status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
