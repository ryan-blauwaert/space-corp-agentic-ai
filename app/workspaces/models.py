from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.base import Base

if TYPE_CHECKING:
    from app.equipment.models import EquipmentUnitRecord, InventoryItemRecord
    from app.facilities.models import FacilityRecord
    from app.operations.models import IncidentRecord, WorkOrderRecord


class WorkspaceRecord(Base):
    """Persistence record for the owner of workspace-scoped operational data."""

    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    facilities: Mapped[list[FacilityRecord]] = relationship(
        back_populates="workspace"
    )
    equipment_units: Mapped[list[EquipmentUnitRecord]] = relationship(
        back_populates="workspace"
    )
    inventory_items: Mapped[list[InventoryItemRecord]] = relationship(
        back_populates="workspace"
    )
    incidents: Mapped[list[IncidentRecord]] = relationship(back_populates="workspace")
    work_orders: Mapped[list[WorkOrderRecord]] = relationship(back_populates="workspace")
