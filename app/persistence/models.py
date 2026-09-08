"""Load all ORM records into SQLAlchemy's shared declarative registry."""

from app.facilities.models import FacilityRecord
from app.workspaces.models import WorkspaceRecord

__all__ = ["FacilityRecord", "WorkspaceRecord"]
