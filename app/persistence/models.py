"""Load all ORM records into SQLAlchemy's shared declarative registry."""

from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
)
from app.facilities.models import FacilityRecord
from app.workspaces.models import WorkspaceRecord

__all__ = [
    "CatalogReleaseRecord",
    "ComponentRecord",
    "EquipmentModelRecord",
    "EquipmentUnitRecord",
    "InventoryItemRecord",
    "FacilityRecord",
    "WorkspaceRecord",
]
