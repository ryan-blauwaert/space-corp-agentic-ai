"""Typed public read responses and bounded query parameters."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pagination import PaginationMetadata, PaginationQuery
from app.equipment.domain import EquipmentOperationalStatus


class EquipmentUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    facility_id: UUID
    equipment_model_id: UUID
    asset_tag: str
    operational_status: EquipmentOperationalStatus
    created_at: datetime
    updated_at: datetime


class EquipmentUnitListResponse(BaseModel):
    items: list[EquipmentUnitResponse]
    pagination: PaginationMetadata


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    facility_id: UUID
    component_id: UUID
    quantity_on_hand: int
    reorder_point: int
    created_at: datetime
    updated_at: datetime


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemResponse]
    pagination: PaginationMetadata


class EquipmentModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    catalog_release_id: UUID
    code: str
    name: str
    created_at: datetime


class EquipmentModelListResponse(BaseModel):
    items: list[EquipmentModelResponse]
    pagination: PaginationMetadata


class ComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    catalog_release_id: UUID
    code: str
    name: str
    created_at: datetime


class ComponentListResponse(BaseModel):
    items: list[ComponentResponse]
    pagination: PaginationMetadata


class EquipmentUnitQuery(PaginationQuery):
    facility_id: UUID | None = None
    equipment_model_id: UUID | None = None
    operational_status: EquipmentOperationalStatus | None = None


class InventoryItemQuery(PaginationQuery):
    facility_id: UUID | None = None
    component_id: UUID | None = None


class CatalogQuery(PaginationQuery):
    catalog_release_id: UUID | None = Field(
        default=None,
        description="Exact catalog release. Omit to browse all releases; no latest-release selection.",
    )
