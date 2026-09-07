from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.base import Base

if TYPE_CHECKING:
    from app.workspaces.models import WorkspaceRecord


class FacilityRecord(Base):
    """SQLAlchemy persistence record for a workspace-owned facility."""

    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint("char_length(code) > 0", name="ck_facilities_code_not_blank"),
        CheckConstraint("char_length(name) > 0", name="ck_facilities_name_not_blank"),
        CheckConstraint(
            "char_length(location) > 0",
            name="ck_facilities_location_not_blank",
        ),
        CheckConstraint(
            "facility_type IN "
            "('lunar_installation', 'orbital_station', 'logistics_depot', "
            "'mission_control_center')",
            name="ck_facilities_type",
        ),
        CheckConstraint(
            "operational_status IN ('operational', 'degraded', 'offline')",
            name="ck_facilities_operational_status",
        ),
        UniqueConstraint("workspace_id", "code", name="uq_facilities_workspace_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str] = mapped_column(String(256), nullable=False)
    operational_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    workspace: Mapped[WorkspaceRecord] = relationship(back_populates="facilities")
