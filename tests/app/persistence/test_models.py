"""Verify ORM records are available when the application imports its database."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "entry_import",
    [
        "from app.main import app; ",
        "from app.operations.models import IncidentRecord; import app.database; ",
    ],
)
def test_application_import_registers_related_orm_models(entry_import: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            entry_import + "from sqlalchemy.orm import configure_mappers; "
            "configure_mappers(); "
            "from app.equipment.models import CatalogReleaseRecord, ComponentRecord, EquipmentModelRecord, EquipmentUnitRecord, InventoryItemRecord; "
            "from app.operations.models import IncidentRecord; "
            "from app.facilities.models import FacilityRecord; "
            "from app.workspaces.models import WorkspaceRecord; "
            "assert FacilityRecord.workspace.property.mapper.class_ is WorkspaceRecord; "
            "assert CatalogReleaseRecord.equipment_models.property.mapper.class_ is EquipmentModelRecord; "
            "assert CatalogReleaseRecord.components.property.mapper.class_ is ComponentRecord; "
            "assert EquipmentModelRecord.components.property.mapper.class_ is ComponentRecord; "
            "assert ComponentRecord.inventory_items.property.mapper.class_ is InventoryItemRecord; "
            "assert EquipmentUnitRecord.facility.property.mapper.class_ is FacilityRecord; "
            "assert FacilityRecord.incidents.property.mapper.class_ is IncidentRecord; "
            "assert WorkspaceRecord.incidents.property.mapper.class_ is IncidentRecord; "
            "assert EquipmentUnitRecord.incidents.property.mapper.class_ is IncidentRecord; "
            "assert IncidentRecord.facility.property.mapper.class_ is FacilityRecord; "
            "assert IncidentRecord.workspace.property.mapper.class_ is WorkspaceRecord; "
            "assert IncidentRecord.equipment_unit.property.mapper.class_ is EquipmentUnitRecord",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
