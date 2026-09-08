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
            "from app.facilities.models import FacilityRecord; "
            "from app.workspaces.models import WorkspaceRecord; "
            "assert FacilityRecord.workspace.property.mapper.class_ is WorkspaceRecord",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
