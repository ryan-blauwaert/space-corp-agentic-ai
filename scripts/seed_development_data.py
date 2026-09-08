"""Populate one local development workspace with repeatable smoke-test data."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Database
from app.facilities.domain import FacilityOperationalStatus, FacilityType
from app.facilities.models import FacilityRecord
from app.workspaces.models import WorkspaceRecord


class SeedConfigurationError(RuntimeError):
    """Raised when development seeding is requested with unsafe configuration."""


@dataclass(frozen=True, slots=True)
class FacilitySeed:
    id: UUID
    code: str
    name: str
    facility_type: FacilityType
    location: str
    operational_status: FacilityOperationalStatus


@dataclass(frozen=True, slots=True)
class SeedResult:
    workspace_id: UUID
    workspace_created: bool
    facilities_created: int
    facilities_refreshed: int


FACILITY_SMOKE_DATA = (
    FacilitySeed(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    ),
    FacilitySeed(
        id=UUID("10000000-0000-4000-8000-000000000002"),
        code="ORB-OPS-01",
        name="Orbital Operations Station",
        facility_type=FacilityType.ORBITAL_STATION,
        location="Low Earth Orbit",
        operational_status=FacilityOperationalStatus.DEGRADED,
    ),
    FacilitySeed(
        id=UUID("10000000-0000-4000-8000-000000000003"),
        code="LOG-OPS-01",
        name="Cislunar Logistics Depot",
        facility_type=FacilityType.LOGISTICS_DEPOT,
        location="Earth-Moon L1",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    ),
)


def require_migration_owner(session: Session) -> str:
    """Require the connected role to own all tables modified by this seed."""
    ownership_rows = session.execute(
        text(
            """
            SELECT current_user, relation.relname, owner.rolname
            FROM pg_class AS relation
            JOIN pg_namespace AS schema ON schema.oid = relation.relnamespace
            JOIN pg_roles AS owner ON owner.oid = relation.relowner
            WHERE schema.nspname = 'public'
              AND relation.relname IN ('workspaces', 'facilities')
              AND relation.relkind = 'r'
            """
        )
    ).all()
    table_owners = {relation_name: owner for _, relation_name, owner in ownership_rows}

    if set(table_owners) != {"workspaces", "facilities"}:
        raise SeedConfigurationError(
            "The workspace and Facility migrations must be applied before seeding."
        )

    current_user = str(ownership_rows[0][0])
    if any(owner != current_user for owner in table_owners.values()):
        raise SeedConfigurationError(
            "SPACE_CORP_MIGRATION_DATABASE_URL must connect as the owner of the "
            "workspace and Facility tables."
        )

    return current_user


def seed_smoke_data(session: Session, workspace_id: UUID) -> SeedResult:
    """Create or restore the small Facility dataset for one workspace."""
    workspace = session.get(WorkspaceRecord, workspace_id)
    workspace_created = workspace is None
    if workspace is None:
        session.add(WorkspaceRecord(id=workspace_id))
        session.flush()

    facilities_created = 0
    facilities_refreshed = 0
    for seed in FACILITY_SMOKE_DATA:
        record = session.scalar(
            select(FacilityRecord).where(
                FacilityRecord.workspace_id == workspace_id,
                FacilityRecord.code == seed.code,
            )
        )
        if record is None:
            record = session.get(FacilityRecord, seed.id)
            if record is not None and record.workspace_id != workspace_id:
                raise SeedConfigurationError(
                    f"Smoke-data Facility ID {seed.id} belongs to another workspace."
                )
        if record is None:
            record = FacilityRecord(id=seed.id, workspace_id=workspace_id)
            session.add(record)
            facilities_created += 1
        else:
            facilities_refreshed += 1

        record.code = seed.code
        record.name = seed.name
        record.facility_type = seed.facility_type.value
        record.location = seed.location
        record.operational_status = seed.operational_status.value

    session.flush()
    return SeedResult(
        workspace_id=workspace_id,
        workspace_created=workspace_created,
        facilities_created=facilities_created,
        facilities_refreshed=facilities_refreshed,
    )


def seed_configured_development_database(settings: Settings) -> SeedResult:
    """Seed the configured local database after enforcing development safeguards."""
    if settings.environment != "development":
        raise SeedConfigurationError(
            "Smoke data can only be seeded when SPACE_CORP_ENVIRONMENT=development."
        )
    if settings.migration_database_url is None:
        raise SeedConfigurationError(
            "SPACE_CORP_MIGRATION_DATABASE_URL must be configured before seeding."
        )
    if settings.default_workspace_id is None:
        raise SeedConfigurationError(
            "SPACE_CORP_DEFAULT_WORKSPACE_ID must be configured before seeding."
        )

    database_name = make_url(str(settings.migration_database_url)).database
    if database_name is None or database_name.startswith("space_corp_test"):
        raise SeedConfigurationError(
            "Development smoke data cannot be seeded into the test database."
        )

    database = Database(str(settings.migration_database_url))
    try:
        with database.session() as session:
            require_migration_owner(session)
            return seed_smoke_data(session, settings.default_workspace_id)
    finally:
        database.dispose()


def main() -> None:
    result = seed_configured_development_database(Settings())
    workspace_action = "created" if result.workspace_created else "reused"
    print(
        f"Workspace {result.workspace_id} {workspace_action}; "
        f"{result.facilities_created} Facilities created and "
        f"{result.facilities_refreshed} refreshed."
    )


if __name__ == "__main__":
    main()
