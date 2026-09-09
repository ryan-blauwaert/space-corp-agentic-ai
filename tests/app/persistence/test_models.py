"""Verify ORM records are available when the application imports its database."""

import subprocess
import sys


def test_application_import_registers_related_orm_models() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from sqlalchemy.orm import configure_mappers; "
            "from app.main import app; "
            "configure_mappers(); "
            "from app.equipment.models import CatalogReleaseRecord, EquipmentModelRecord, EquipmentUnitRecord; "
            "from app.facilities.models import FacilityRecord; "
            "from app.workspaces.models import WorkspaceRecord; "
            "assert FacilityRecord.workspace.property.mapper.class_ is WorkspaceRecord; "
            "assert CatalogReleaseRecord.equipment_models.property.mapper.class_ is EquipmentModelRecord; "
            "assert EquipmentUnitRecord.facility.property.mapper.class_ is FacilityRecord",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
