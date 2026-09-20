"""SQLAlchemy records for shared equipment catalog data and deployed units."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    and_,
    Column,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.equipment.domain import (
    CATALOG_RELEASE_CODE_MAX_LENGTH,
    COMPONENT_CODE_MAX_LENGTH,
    COMPONENT_NAME_MAX_LENGTH,
    EQUIPMENT_MODEL_CODE_MAX_LENGTH,
    EQUIPMENT_MODEL_NAME_MAX_LENGTH,
    EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH,
)
from app.persistence.base import Base

if TYPE_CHECKING:
    from app.facilities.models import FacilityRecord
    from app.operations.models import IncidentRecord
    from app.workspaces.models import WorkspaceRecord


# Match Python str.strip(), including Unicode whitespace.
_REQUIRED_TEXT_WHITESPACE = (
    '\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020'
    '\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006'
    '\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000'
)


equipment_model_components = Table(
    "equipment_model_components",
    Base.metadata,
    Column("catalog_release_id", Uuid, nullable=False),
    Column("equipment_model_id", Uuid, nullable=False),
    Column("component_id", Uuid, nullable=False),
    ForeignKeyConstraint(
        ["catalog_release_id", "equipment_model_id"],
        ["equipment_models.catalog_release_id", "equipment_models.id"],
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["catalog_release_id", "component_id"],
        ["components.catalog_release_id", "components.id"],
        ondelete="RESTRICT",
    ),
    PrimaryKeyConstraint(
        "equipment_model_id",
        "component_id",
        name="pk_equipment_model_components",
    ),
)


class CatalogReleaseRecord(Base):
    """Persistence record for one immutable shared catalog release identity."""

    __tablename__ = "catalog_releases"
    __table_args__ = (
        CheckConstraint(
            f"char_length(btrim(code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_catalog_releases_code_not_blank",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(
        String(CATALOG_RELEASE_CODE_MAX_LENGTH), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    equipment_models: Mapped[list[EquipmentModelRecord]] = relationship(
        back_populates="catalog_release"
    )
    components: Mapped[list[ComponentRecord]] = relationship(
        back_populates="catalog_release"
    )


class EquipmentModelRecord(Base):
    """Persistence record for an immutable equipment-model revision."""

    __tablename__ = "equipment_models"
    __table_args__ = (
        CheckConstraint(
            f"char_length(btrim(code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_equipment_models_code_not_blank",
        ),
        CheckConstraint(
            f"char_length(btrim(name, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_equipment_models_name_not_blank",
        ),
        UniqueConstraint(
            "catalog_release_id",
            "code",
            name="uq_equipment_models_release_code",
        ),
        UniqueConstraint(
            "catalog_release_id",
            "id",
            name="uq_equipment_models_release_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    catalog_release_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_releases.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(
        String(EQUIPMENT_MODEL_CODE_MAX_LENGTH), nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(EQUIPMENT_MODEL_NAME_MAX_LENGTH), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    catalog_release: Mapped[CatalogReleaseRecord] = relationship(
        back_populates="equipment_models"
    )
    equipment_units: Mapped[list[EquipmentUnitRecord]] = relationship(
        back_populates="equipment_model"
    )
    components: Mapped[list[ComponentRecord]] = relationship(
        secondary=equipment_model_components,
        back_populates="equipment_models",
    )


class ComponentRecord(Base):
    """Persistence record for an immutable component revision."""

    __tablename__ = "components"
    __table_args__ = (
        CheckConstraint(
            f"char_length(btrim(code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_components_code_not_blank",
        ),
        CheckConstraint(
            f"char_length(btrim(name, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_components_name_not_blank",
        ),
        UniqueConstraint(
            "catalog_release_id", "code", name="uq_components_release_code"
        ),
        UniqueConstraint(
            "catalog_release_id", "id", name="uq_components_release_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    catalog_release_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_releases.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(COMPONENT_CODE_MAX_LENGTH), nullable=False)
    name: Mapped[str] = mapped_column(String(COMPONENT_NAME_MAX_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    catalog_release: Mapped[CatalogReleaseRecord] = relationship(
        back_populates="components"
    )
    equipment_models: Mapped[list[EquipmentModelRecord]] = relationship(
        secondary=equipment_model_components,
        back_populates="components",
    )
    inventory_items: Mapped[list[InventoryItemRecord]] = relationship(
        back_populates="component"
    )


class InventoryItemRecord(Base):
    """Persistence record for workspace-owned component inventory at a Facility."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "facility_id"],
            ["facilities.workspace_id", "facilities.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "quantity_on_hand >= 0",
            name="ck_inventory_items_quantity_on_hand_nonnegative",
        ),
        CheckConstraint(
            "reorder_point >= 0",
            name="ck_inventory_items_reorder_point_nonnegative",
        ),
        UniqueConstraint(
            "workspace_id",
            "facility_id",
            "component_id",
            name="uq_inventory_items_workspace_facility_component",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    facility_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    component_id: Mapped[UUID] = mapped_column(
        ForeignKey("components.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    workspace: Mapped[WorkspaceRecord] = relationship(back_populates="inventory_items")
    facility: Mapped[FacilityRecord] = relationship(
        back_populates="inventory_items",
        primaryjoin=(
            "and_(InventoryItemRecord.workspace_id == FacilityRecord.workspace_id, "
            "foreign(InventoryItemRecord.facility_id) == FacilityRecord.id)"
        ),
        foreign_keys="[InventoryItemRecord.facility_id]",
    )
    component: Mapped[ComponentRecord] = relationship(back_populates="inventory_items")


class EquipmentUnitRecord(Base):
    """Persistence record for a workspace-owned deployed equipment unit."""

    __tablename__ = "equipment_units"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "facility_id"],
            ["facilities.workspace_id", "facilities.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"char_length(btrim(asset_tag, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_equipment_units_asset_tag_not_blank",
        ),
        CheckConstraint(
            "operational_status IN ('operational', 'degraded', 'offline', 'maintenance')",
            name="ck_equipment_units_operational_status",
        ),
        UniqueConstraint(
            "workspace_id", "asset_tag", name="uq_equipment_units_workspace_asset_tag"
        ),
        UniqueConstraint(
            "workspace_id", "id", name="uq_equipment_units_workspace_id"
        ),
        UniqueConstraint(
            "workspace_id",
            "facility_id",
            "id",
            name="uq_equipment_units_workspace_facility_id",
        ),
        Index(
            "ix_equipment_units_workspace_facility_status",
            "workspace_id",
            "facility_id",
            "operational_status",
        ),
        Index(
            "ix_equipment_units_workspace_model",
            "workspace_id",
            "equipment_model_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    facility_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    equipment_model_id: Mapped[UUID] = mapped_column(
        ForeignKey("equipment_models.id", ondelete="RESTRICT"), nullable=False
    )
    asset_tag: Mapped[str] = mapped_column(
        String(EQUIPMENT_UNIT_ASSET_TAG_MAX_LENGTH), nullable=False
    )
    operational_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    workspace: Mapped[WorkspaceRecord] = relationship(back_populates="equipment_units")
    facility: Mapped[FacilityRecord] = relationship(
        back_populates="equipment_units",
        primaryjoin=(
            "and_(EquipmentUnitRecord.workspace_id == FacilityRecord.workspace_id, "
            "foreign(EquipmentUnitRecord.facility_id) == FacilityRecord.id)"
        ),
        foreign_keys="[EquipmentUnitRecord.facility_id]",
    )
    equipment_model: Mapped[EquipmentModelRecord] = relationship(
        back_populates="equipment_units"
    )
    incidents: Mapped[list[IncidentRecord]] = relationship(
        back_populates="equipment_unit",
        primaryjoin=(
            "and_(EquipmentUnitRecord.workspace_id == IncidentRecord.workspace_id, "
            "EquipmentUnitRecord.facility_id == IncidentRecord.facility_id, "
            "EquipmentUnitRecord.id == foreign(IncidentRecord.equipment_unit_id))"
        ),
        foreign_keys="[IncidentRecord.equipment_unit_id]",
    )
