"""Repositories for equipment catalog records and workspace-owned units."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.equipment.domain import (
    CatalogRelease,
    Component,
    EquipmentModel,
    EquipmentOperationalStatus,
    EquipmentUnit,
    InventoryItem,
    NewCatalogRelease,
    NewComponent,
    NewEquipmentModel,
    NewEquipmentUnit,
    NewInventoryItem,
    _validate_nonnegative_whole_number,
)
from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
    equipment_model_components,
)


class CatalogRepository(Protocol):
    """Persistence operations for shared catalog reference data."""

    def read_models_page(
        self,
        *,
        catalog_release_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EquipmentModel], int]:
        """Return shared revisions, optionally restricted to one release."""

    def read_components_page(
        self,
        *,
        catalog_release_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Component], int]:
        """Return shared revisions, optionally restricted to one release."""

    def read_compatible_components(
        self,
        equipment_model_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Component], int]:
        """Return compatible components for an exact shared model revision."""

    def create_release(self, release: NewCatalogRelease) -> CatalogRelease:
        """Create one catalog release identity."""

    def create_model(self, model: NewEquipmentModel) -> EquipmentModel:
        """Create one equipment-model revision in a catalog release."""

    def get_model_by_id(self, equipment_model_id: UUID) -> EquipmentModel | None:
        """Return an equipment model by its globally unique revision identity."""

    def create_component(self, component: NewComponent) -> Component:
        """Create one component revision in a catalog release."""

    def get_component_by_id(self, component_id: UUID) -> Component | None:
        """Return a component by its globally unique revision identity."""

    def link_model_to_component(
        self,
        catalog_release_id: UUID,
        equipment_model_id: UUID,
        component_id: UUID,
    ) -> None:
        """Record compatibility between same-release model and component revisions."""


class EquipmentUnitRepository(Protocol):
    """Persistence operations for workspace-owned deployed equipment units."""

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        equipment_model_id: UUID | None = None,
        operational_status: EquipmentOperationalStatus | None = None,
    ) -> tuple[list[EquipmentUnit], int]:
        """Return a filtered workspace page and its total before pagination."""

    def create(self, workspace_id: UUID, equipment_unit: NewEquipmentUnit) -> EquipmentUnit:
        """Create a unit owned by the supplied workspace."""

    def get_by_id(self, workspace_id: UUID, equipment_unit_id: UUID) -> EquipmentUnit | None:
        """Return a unit only when it belongs to the supplied workspace."""

    def list_by_facility(
        self,
        workspace_id: UUID,
        facility_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EquipmentUnit]:
        """Return one page of the workspace's units at a Facility."""

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        """Return the number of workspace-owned units at a Facility."""

    def update_operational_status(
        self,
        workspace_id: UUID,
        equipment_unit_id: UUID,
        operational_status: EquipmentOperationalStatus,
    ) -> EquipmentUnit | None:
        """Update only the current operational status of a workspace-owned unit."""


class InventoryItemRepository(Protocol):
    """Persistence operations for workspace-owned Facility component stock."""

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        component_id: UUID | None = None,
    ) -> tuple[list[InventoryItem], int]:
        """Return a filtered workspace page and its total before pagination."""

    def create(self, workspace_id: UUID, inventory_item: NewInventoryItem) -> InventoryItem:
        """Create inventory owned by the supplied workspace."""

    def get_by_id(self, workspace_id: UUID, inventory_item_id: UUID) -> InventoryItem | None:
        """Return inventory only when it belongs to the supplied workspace."""

    def list_by_facility(
        self,
        workspace_id: UUID,
        facility_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InventoryItem]:
        """Return one page of the workspace's inventory at a Facility."""

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        """Return the number of inventory records at a workspace Facility."""

    def update_stock_levels(
        self,
        workspace_id: UUID,
        inventory_item_id: UUID,
        *,
        quantity_on_hand: int,
        reorder_point: int,
    ) -> InventoryItem | None:
        """Update only the mutable stock values of workspace-owned inventory."""


class SqlAlchemyCatalogRepository:
    """SQLAlchemy implementation for shared catalog reference data."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read_models_page(
        self,
        *,
        catalog_release_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EquipmentModel], int]:
        statement = select(EquipmentModelRecord)
        if catalog_release_id is not None:
            statement = statement.where(
                EquipmentModelRecord.catalog_release_id == catalog_release_id
            )
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        records = self._session.scalars(
            statement.order_by(EquipmentModelRecord.code, EquipmentModelRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return [_equipment_model_to_domain(record) for record in records], total

    def read_components_page(
        self,
        *,
        catalog_release_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Component], int]:
        statement = select(ComponentRecord)
        if catalog_release_id is not None:
            statement = statement.where(ComponentRecord.catalog_release_id == catalog_release_id)
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        records = self._session.scalars(
            statement.order_by(ComponentRecord.code, ComponentRecord.id).limit(limit).offset(offset)
        )
        return [_component_to_domain(record) for record in records], total

    def read_compatible_components(
        self,
        equipment_model_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Component], int]:
        statement = (
            select(ComponentRecord)
            .join(
                equipment_model_components,
                equipment_model_components.c.component_id == ComponentRecord.id,
            )
            .where(equipment_model_components.c.equipment_model_id == equipment_model_id)
        )
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        records = self._session.scalars(
            statement.order_by(ComponentRecord.code, ComponentRecord.id).limit(limit).offset(offset)
        )
        return [_component_to_domain(record) for record in records], total

    def create_release(self, release: NewCatalogRelease) -> CatalogRelease:
        record = CatalogReleaseRecord(code=release.code)
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return _catalog_release_to_domain(record)

    def create_model(self, model: NewEquipmentModel) -> EquipmentModel:
        record = EquipmentModelRecord(
            catalog_release_id=model.catalog_release_id,
            code=model.code,
            name=model.name,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return _equipment_model_to_domain(record)

    def get_model_by_id(self, equipment_model_id: UUID) -> EquipmentModel | None:
        record = self._session.get(EquipmentModelRecord, equipment_model_id)
        return None if record is None else _equipment_model_to_domain(record)

    def create_component(self, component: NewComponent) -> Component:
        record = ComponentRecord(
            catalog_release_id=component.catalog_release_id,
            code=component.code,
            name=component.name,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return _component_to_domain(record)

    def get_component_by_id(self, component_id: UUID) -> Component | None:
        record = self._session.get(ComponentRecord, component_id)
        return None if record is None else _component_to_domain(record)

    def link_model_to_component(
        self,
        catalog_release_id: UUID,
        equipment_model_id: UUID,
        component_id: UUID,
    ) -> None:
        self._session.execute(
            equipment_model_components.insert().values(
                catalog_release_id=catalog_release_id,
                equipment_model_id=equipment_model_id,
                component_id=component_id,
            )
        )
        self._session.flush()


class SqlAlchemyEquipmentUnitRepository:
    """SQLAlchemy implementation of workspace-scoped unit persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        equipment_model_id: UUID | None = None,
        operational_status: EquipmentOperationalStatus | None = None,
    ) -> tuple[list[EquipmentUnit], int]:
        statement = select(EquipmentUnitRecord).where(
            EquipmentUnitRecord.workspace_id == workspace_id
        )
        if facility_id is not None:
            statement = statement.where(EquipmentUnitRecord.facility_id == facility_id)
        if equipment_model_id is not None:
            statement = statement.where(
                EquipmentUnitRecord.equipment_model_id == equipment_model_id
            )
        if operational_status is not None:
            statement = statement.where(
                EquipmentUnitRecord.operational_status == operational_status
            )
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        records = self._session.scalars(
            statement.order_by(EquipmentUnitRecord.asset_tag, EquipmentUnitRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return [_equipment_unit_to_domain(record) for record in records], total

    def create(self, workspace_id: UUID, equipment_unit: NewEquipmentUnit) -> EquipmentUnit:
        record = EquipmentUnitRecord(
            workspace_id=workspace_id,
            facility_id=equipment_unit.facility_id,
            equipment_model_id=equipment_unit.equipment_model_id,
            asset_tag=equipment_unit.asset_tag,
            operational_status=equipment_unit.operational_status.value,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return _equipment_unit_to_domain(record)

    def get_by_id(self, workspace_id: UUID, equipment_unit_id: UUID) -> EquipmentUnit | None:
        record = self._session.scalar(
            select(EquipmentUnitRecord).where(
                EquipmentUnitRecord.workspace_id == workspace_id,
                EquipmentUnitRecord.id == equipment_unit_id,
            )
        )
        return None if record is None else _equipment_unit_to_domain(record)

    def list_by_facility(
        self,
        workspace_id: UUID,
        facility_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EquipmentUnit]:
        statement = (
            select(EquipmentUnitRecord)
            .where(
                EquipmentUnitRecord.workspace_id == workspace_id,
                EquipmentUnitRecord.facility_id == facility_id,
            )
            .order_by(EquipmentUnitRecord.asset_tag)
            .limit(limit)
            .offset(offset)
        )
        return [_equipment_unit_to_domain(record) for record in self._session.scalars(statement)]

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        statement = select(func.count()).where(
            EquipmentUnitRecord.workspace_id == workspace_id,
            EquipmentUnitRecord.facility_id == facility_id,
        )
        return self._session.scalar(statement) or 0

    def update_operational_status(
        self,
        workspace_id: UUID,
        equipment_unit_id: UUID,
        operational_status: EquipmentOperationalStatus,
    ) -> EquipmentUnit | None:
        record = self._session.scalar(
            select(EquipmentUnitRecord).where(
                EquipmentUnitRecord.workspace_id == workspace_id,
                EquipmentUnitRecord.id == equipment_unit_id,
            )
        )
        if record is None:
            return None

        record.operational_status = operational_status.value
        self._session.flush()
        self._session.refresh(record)
        return _equipment_unit_to_domain(record)


class SqlAlchemyInventoryItemRepository:
    """SQLAlchemy implementation of workspace-scoped inventory persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read_page(
        self,
        workspace_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        facility_id: UUID | None = None,
        component_id: UUID | None = None,
    ) -> tuple[list[InventoryItem], int]:
        statement = select(InventoryItemRecord).where(
            InventoryItemRecord.workspace_id == workspace_id
        )
        if facility_id is not None:
            statement = statement.where(InventoryItemRecord.facility_id == facility_id)
        if component_id is not None:
            statement = statement.where(InventoryItemRecord.component_id == component_id)
        total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        records = self._session.scalars(
            statement.order_by(InventoryItemRecord.id).limit(limit).offset(offset)
        )
        return [_inventory_item_to_domain(record) for record in records], total

    def create(self, workspace_id: UUID, inventory_item: NewInventoryItem) -> InventoryItem:
        record = InventoryItemRecord(
            workspace_id=workspace_id,
            facility_id=inventory_item.facility_id,
            component_id=inventory_item.component_id,
            quantity_on_hand=inventory_item.quantity_on_hand,
            reorder_point=inventory_item.reorder_point,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return _inventory_item_to_domain(record)

    def get_by_id(self, workspace_id: UUID, inventory_item_id: UUID) -> InventoryItem | None:
        record = self._session.scalar(
            select(InventoryItemRecord).where(
                InventoryItemRecord.workspace_id == workspace_id,
                InventoryItemRecord.id == inventory_item_id,
            )
        )
        return None if record is None else _inventory_item_to_domain(record)

    def list_by_facility(
        self,
        workspace_id: UUID,
        facility_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InventoryItem]:
        statement = (
            select(InventoryItemRecord)
            .where(
                InventoryItemRecord.workspace_id == workspace_id,
                InventoryItemRecord.facility_id == facility_id,
            )
            .order_by(InventoryItemRecord.component_id)
            .limit(limit)
            .offset(offset)
        )
        return [_inventory_item_to_domain(record) for record in self._session.scalars(statement)]

    def count_by_facility(self, workspace_id: UUID, facility_id: UUID) -> int:
        statement = select(func.count()).where(
            InventoryItemRecord.workspace_id == workspace_id,
            InventoryItemRecord.facility_id == facility_id,
        )
        return self._session.scalar(statement) or 0

    def update_stock_levels(
        self,
        workspace_id: UUID,
        inventory_item_id: UUID,
        *,
        quantity_on_hand: int,
        reorder_point: int,
    ) -> InventoryItem | None:
        _validate_nonnegative_whole_number("Quantity on hand", quantity_on_hand)
        _validate_nonnegative_whole_number("Reorder point", reorder_point)
        record = self._session.scalar(
            select(InventoryItemRecord).where(
                InventoryItemRecord.workspace_id == workspace_id,
                InventoryItemRecord.id == inventory_item_id,
            )
        )
        if record is None:
            return None

        record.quantity_on_hand = quantity_on_hand
        record.reorder_point = reorder_point
        self._session.flush()
        self._session.refresh(record)
        return _inventory_item_to_domain(record)


def _catalog_release_to_domain(record: CatalogReleaseRecord) -> CatalogRelease:
    return CatalogRelease(id=record.id, code=record.code, created_at=record.created_at)


def _equipment_model_to_domain(record: EquipmentModelRecord) -> EquipmentModel:
    return EquipmentModel(
        id=record.id,
        catalog_release_id=record.catalog_release_id,
        code=record.code,
        name=record.name,
        created_at=record.created_at,
    )


def _component_to_domain(record: ComponentRecord) -> Component:
    return Component(
        id=record.id,
        catalog_release_id=record.catalog_release_id,
        code=record.code,
        name=record.name,
        created_at=record.created_at,
    )


def _inventory_item_to_domain(record: InventoryItemRecord) -> InventoryItem:
    return InventoryItem(
        id=record.id,
        workspace_id=record.workspace_id,
        facility_id=record.facility_id,
        component_id=record.component_id,
        quantity_on_hand=record.quantity_on_hand,
        reorder_point=record.reorder_point,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _equipment_unit_to_domain(record: EquipmentUnitRecord) -> EquipmentUnit:
    return EquipmentUnit(
        id=record.id,
        workspace_id=record.workspace_id,
        facility_id=record.facility_id,
        equipment_model_id=record.equipment_model_id,
        asset_tag=record.asset_tag,
        operational_status=EquipmentOperationalStatus(record.operational_status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
