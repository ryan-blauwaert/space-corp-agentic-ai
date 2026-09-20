"""SQLAlchemy records for workspace-owned operational incidents."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.operations.domain import (
    INCIDENT_FAULT_CODE_MAX_LENGTH,
    INCIDENT_REFERENCE_CODE_MAX_LENGTH,
    WORK_ORDER_REFERENCE_CODE_MAX_LENGTH,
)
from app.persistence.base import Base

if TYPE_CHECKING:
    from app.equipment.models import EquipmentUnitRecord
    from app.facilities.models import FacilityRecord
    from app.workspaces.models import WorkspaceRecord


# Match Python str.strip(), including Unicode whitespace.
_REQUIRED_TEXT_WHITESPACE = (
    '\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020'
    '\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006'
    '\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000'
)


class IncidentRecord(Base):
    """Persistence record for a workspace-owned operational incident."""

    __tablename__ = "incidents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "facility_id"],
            ["facilities.workspace_id", "facilities.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "facility_id", "equipment_unit_id"],
            [
                "equipment_units.workspace_id",
                "equipment_units.facility_id",
                "equipment_units.id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"char_length(btrim(reference_code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_incidents_reference_code_not_blank",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incidents_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'resolved')",
            name="ck_incidents_status",
        ),
        CheckConstraint(
            "fault_code IS NULL OR ("
            f"char_length(btrim(fault_code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0 "
            f"AND fault_code = upper(btrim(fault_code, U&'{_REQUIRED_TEXT_WHITESPACE}'))"
            ")",
            name="ck_incidents_fault_code_normalized",
        ),
        CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL)",
            name="ck_incidents_resolved_at_matches_status",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= occurred_at",
            name="ck_incidents_resolved_at_after_occurred_at",
        ),
        UniqueConstraint(
            "workspace_id", "reference_code", name="uq_incidents_workspace_reference_code"
        ),
        UniqueConstraint("workspace_id", "id", name="uq_incidents_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "facility_id",
            "id",
            name="uq_incidents_workspace_facility_id",
        ),
        Index(
            "ix_incidents_workspace_facility_status",
            "workspace_id",
            "facility_id",
            "status",
        ),
        Index(
            "ix_incidents_workspace_equipment_unit_status",
            "workspace_id",
            "equipment_unit_id",
            "status",
        ),
        Index(
            "ix_incidents_workspace_unit_fault_occurred",
            "workspace_id",
            "equipment_unit_id",
            "fault_code",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    facility_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    equipment_unit_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reference_code: Mapped[str] = mapped_column(
        String(INCIDENT_REFERENCE_CODE_MAX_LENGTH), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fault_code: Mapped[str | None] = mapped_column(
        String(INCIDENT_FAULT_CODE_MAX_LENGTH), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    workspace: Mapped[WorkspaceRecord] = relationship(back_populates="incidents")
    facility: Mapped[FacilityRecord] = relationship(
        back_populates="incidents",
        primaryjoin=(
            "and_(IncidentRecord.workspace_id == FacilityRecord.workspace_id, "
            "foreign(IncidentRecord.facility_id) == FacilityRecord.id)"
        ),
        foreign_keys="[IncidentRecord.facility_id]",
    )
    equipment_unit: Mapped[EquipmentUnitRecord | None] = relationship(
        back_populates="incidents",
        primaryjoin=(
            "and_(IncidentRecord.workspace_id == EquipmentUnitRecord.workspace_id, "
            "IncidentRecord.facility_id == EquipmentUnitRecord.facility_id, "
            "foreign(IncidentRecord.equipment_unit_id) == EquipmentUnitRecord.id)"
        ),
        foreign_keys="[IncidentRecord.equipment_unit_id]",
    )
    originating_work_orders: Mapped[list[WorkOrderRecord]] = relationship(
        back_populates="originating_incident",
        primaryjoin=(
            "and_(IncidentRecord.workspace_id == WorkOrderRecord.workspace_id, "
            "IncidentRecord.facility_id == WorkOrderRecord.facility_id, "
            "IncidentRecord.id == foreign(WorkOrderRecord.originating_incident_id))"
        ),
        foreign_keys="[WorkOrderRecord.originating_incident_id]",
    )


class WorkOrderRecord(Base):
    """Persistence record for workspace-owned maintenance work."""

    __tablename__ = "work_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "facility_id"],
            ["facilities.workspace_id", "facilities.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "facility_id", "originating_incident_id"],
            ["incidents.workspace_id", "incidents.facility_id", "incidents.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "facility_id", "target_equipment_unit_id"],
            [
                "equipment_units.workspace_id",
                "equipment_units.facility_id",
                "equipment_units.id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"char_length(btrim(reference_code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_work_orders_reference_code_not_blank",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_work_orders_priority",
        ),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'blocked', 'completed', 'cancelled')",
            name="ck_work_orders_status",
        ),
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="ck_work_orders_completed_at_matches_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_work_orders_completed_at_after_created_at",
        ),
        UniqueConstraint(
            "workspace_id", "reference_code", name="uq_work_orders_workspace_reference_code"
        ),
        UniqueConstraint("workspace_id", "id", name="uq_work_orders_workspace_id"),
        UniqueConstraint(
            "workspace_id", "facility_id", "id", name="uq_work_orders_workspace_facility_id"
        ),
        Index(
            "ix_work_orders_workspace_facility_status_priority",
            "workspace_id", "facility_id", "status", "priority",
        ),
        Index(
            "ix_work_orders_workspace_facility_due_at",
            "workspace_id", "facility_id", "due_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    facility_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    originating_incident_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    target_equipment_unit_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reference_code: Mapped[str] = mapped_column(
        String(WORK_ORDER_REFERENCE_CODE_MAX_LENGTH), nullable=False
    )
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    workspace: Mapped[WorkspaceRecord] = relationship(back_populates="work_orders")
    facility: Mapped[FacilityRecord] = relationship(
        back_populates="work_orders",
        primaryjoin=(
            "and_(WorkOrderRecord.workspace_id == FacilityRecord.workspace_id, "
            "foreign(WorkOrderRecord.facility_id) == FacilityRecord.id)"
        ),
        foreign_keys="[WorkOrderRecord.facility_id]",
    )
    originating_incident: Mapped[IncidentRecord | None] = relationship(
        back_populates="originating_work_orders",
        primaryjoin=(
            "and_(WorkOrderRecord.workspace_id == IncidentRecord.workspace_id, "
            "WorkOrderRecord.facility_id == IncidentRecord.facility_id, "
            "foreign(WorkOrderRecord.originating_incident_id) == IncidentRecord.id)"
        ),
        foreign_keys="[WorkOrderRecord.originating_incident_id]",
    )
    target_equipment_unit: Mapped[EquipmentUnitRecord | None] = relationship(
        back_populates="targeted_work_orders",
        primaryjoin=(
            "and_(WorkOrderRecord.workspace_id == EquipmentUnitRecord.workspace_id, "
            "WorkOrderRecord.facility_id == EquipmentUnitRecord.facility_id, "
            "foreign(WorkOrderRecord.target_equipment_unit_id) == EquipmentUnitRecord.id)"
        ),
        foreign_keys="[WorkOrderRecord.target_equipment_unit_id]",
    )
