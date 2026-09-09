"""Repositories for equipment catalog records and workspace-owned units."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.equipment.domain import (
    CatalogRelease,
    EquipmentModel,
    EquipmentOperationalStatus,
    EquipmentUnit,
    NewCatalogRelease,
    NewEquipmentModel,
    NewEquipmentUnit,
)
from app.equipment.models import (
    CatalogReleaseRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
)


class CatalogRepository(Protocol):
    """Persistence operations for shared catalog reference data."""

    def create_release(self, release: NewCatalogRelease) -> CatalogRelease:
        """Create one catalog release identity."""

    def create_model(self, model: NewEquipmentModel) -> EquipmentModel:
        """Create one equipment-model revision in a catalog release."""

    def get_model_by_id(self, equipment_model_id: UUID) -> EquipmentModel | None:
        """Return an equipment model by its globally unique revision identity."""


class EquipmentUnitRepository(Protocol):
    """Persistence operations for workspace-owned deployed equipment units."""

    def create(self, workspace_id: UUID, equipment_unit: NewEquipmentUnit) -> EquipmentUnit:
        """Create a unit owned by the supplied workspace."""

    def get_by_id(
        self, workspace_id: UUID, equipment_unit_id: UUID
    ) -> EquipmentUnit | None:
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


class SqlAlchemyCatalogRepository:
    """SQLAlchemy implementation for shared catalog reference data."""

    def __init__(self, session: Session) -> None:
        self._session = session

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


class SqlAlchemyEquipmentUnitRepository:
    """SQLAlchemy implementation of workspace-scoped unit persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

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

    def get_by_id(
        self, workspace_id: UUID, equipment_unit_id: UUID
    ) -> EquipmentUnit | None:
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
