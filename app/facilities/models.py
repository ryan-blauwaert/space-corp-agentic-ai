from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    and_,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.facilities.domain import (
    FACILITY_CODE_MAX_LENGTH,
    FACILITY_LOCATION_MAX_LENGTH,
    FACILITY_NAME_MAX_LENGTH,
)
from app.persistence.base import Base

if TYPE_CHECKING:
    from app.equipment.models import EquipmentUnitRecord
    from app.workspaces.models import WorkspaceRecord


# Match Python str.strip(), including Unicode whitespace.
_REQUIRED_TEXT_WHITESPACE = (
    '\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020'
    '\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006'
    '\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000'
)


class FacilityRecord(Base):
    """SQLAlchemy persistence record for a workspace-owned facility."""

    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint(
            f"char_length(btrim(code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_facilities_code_not_blank",
        ),
        CheckConstraint(
            f"char_length(btrim(name, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_facilities_name_not_blank",
        ),
        CheckConstraint(
            f"char_length(btrim(location, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
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
        UniqueConstraint("workspace_id", "id", name="uq_facilities_workspace_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(FACILITY_CODE_MAX_LENGTH), nullable=False)
    name: Mapped[str] = mapped_column(String(FACILITY_NAME_MAX_LENGTH), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str] = mapped_column(
        String(FACILITY_LOCATION_MAX_LENGTH), nullable=False
    )
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
    equipment_units: Mapped[list[EquipmentUnitRecord]] = relationship(
        back_populates="facility",
        primaryjoin=(
            "and_(FacilityRecord.workspace_id == EquipmentUnitRecord.workspace_id, "
            "FacilityRecord.id == foreign(EquipmentUnitRecord.facility_id))"
        ),
        foreign_keys="[EquipmentUnitRecord.facility_id]",
    )
