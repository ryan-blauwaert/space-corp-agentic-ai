"""Load all ORM records into SQLAlchemy's shared declarative registry."""

from app.equipment.models import (
    CatalogReleaseRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
)
from app.facilities.models import FacilityRecord
from app.workspaces.models import WorkspaceRecord

__all__ = [
    "CatalogReleaseRecord",
    "EquipmentModelRecord",
    "EquipmentUnitRecord",
    "FacilityRecord",
    "WorkspaceRecord",
]
