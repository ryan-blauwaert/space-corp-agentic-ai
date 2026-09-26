from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select

from app.database import Database
from app.facilities.models import FacilityRecord
from app.workspaces.models import WorkspaceRecord
from scripts.bootstrap_development import ROOT
from scripts.dataset_manifest import load_manifest
from scripts.facility_locations import FACILITY_LOCATIONS, facility_body_or_system
from scripts.seed_dataset import baseline_rows


def test_frozen_baseline_gets_additive_location_context():
    rows = baseline_rows(load_manifest(), uuid4())[0][1]
    assert len(rows) == 5
    assert {row["code"]: row["body_or_system"] for row in rows} == {
        "LUN-OPS-01": "Earth’s Moon",
        "LUN-OPS-02": "Earth’s Moon",
        "MCC-OPS-01": "Earth",
        "ORB-OPS-01": "Earth",
        "LOG-OPS-01": "Earth–Moon system",
    }
    assert facility_body_or_system("LUN-OPS-01", "New station", "Mare Imbrium") is None
    assert facility_body_or_system("LUN-OPS-01", "Lunar Operations One", "Europa") is None


@pytest.mark.integration
def test_migration_backfills_known_facilities_and_preserves_existing_data(migrated_database):
    database = Database(migrated_database)
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["migration_database_url"] = migrated_database
    workspace = uuid4()
    try:
        with database.session() as session:
            session.add(WorkspaceRecord(id=workspace))
            session.flush()
            for code, name, location in FACILITY_LOCATIONS:
                session.add(
                    FacilityRecord(
                        workspace_id=workspace,
                        code=code,
                        name=name,
                        location=location,
                        facility_type="logistics_depot",
                        operational_status="degraded",
                    )
                )
            session.add(
                FacilityRecord(
                    workspace_id=workspace,
                    code="CUSTOM",
                    name="Custom lunar station",
                    location="Mare Imbrium",
                    facility_type="lunar_installation",
                    operational_status="offline",
                )
            )
        columns = [
            column for column in FacilityRecord.__table__.columns if column.name != "body_or_system"
        ]
        with database.session() as session:
            before = session.execute(
                select(*columns)
                .where(FacilityRecord.workspace_id == workspace)
                .order_by(FacilityRecord.code)
            ).all()
        command.downgrade(config, "0011_query_catalog_pin")
        command.upgrade(config, "head")
        with database.session() as session:
            after = session.execute(
                select(*columns)
                .where(FacilityRecord.workspace_id == workspace)
                .order_by(FacilityRecord.code)
            ).all()
            assert after == before
            for record in session.scalars(
                select(FacilityRecord).where(FacilityRecord.workspace_id == workspace)
            ):
                assert record.body_or_system == facility_body_or_system(
                    record.code, record.name, record.location
                )
        command.upgrade(config, "head")  # Reapplying is harmless.
    finally:
        command.upgrade(config, "head")
        with database.session() as session:
            session.execute(delete(FacilityRecord).where(FacilityRecord.workspace_id == workspace))
            session.execute(delete(WorkspaceRecord).where(WorkspaceRecord.id == workspace))
        database.dispose()
