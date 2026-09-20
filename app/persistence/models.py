"""Load all ORM records into SQLAlchemy's shared declarative registry."""

from app.baselines.models import BaselineRecord
from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
)
from app.operations.models import IncidentRecord, WorkOrderRecord
from app.facilities.models import FacilityRecord
from app.workspaces.models import WorkspaceRecord

__all__ = [
    "BaselineRecord",
    "CatalogReleaseRecord",
    "ComponentRecord",
    "EquipmentModelRecord",
    "EquipmentUnitRecord",
    "InventoryItemRecord",
    "IncidentRecord",
    "WorkOrderRecord",
    "FacilityRecord",
    "WorkspaceRecord",
]
