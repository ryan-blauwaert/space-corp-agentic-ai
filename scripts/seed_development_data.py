"""Populate one local development workspace with repeatable smoke-test data."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Database
from app.equipment.domain import EquipmentOperationalStatus
from app.equipment.models import (
    CatalogReleaseRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
)
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
class CatalogReleaseSeed:
    id: UUID
    code: str


@dataclass(frozen=True, slots=True)
class EquipmentModelSeed:
    id: UUID
    catalog_release_id: UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class EquipmentUnitSeed:
    id: UUID
    facility_id: UUID
    equipment_model_id: UUID
    asset_tag: str
    operational_status: EquipmentOperationalStatus


@dataclass(frozen=True, slots=True)
class SeedResult:
    workspace_id: UUID
    workspace_created: bool
    catalog_releases_created: int
    catalog_releases_refreshed: int
    equipment_models_created: int
    equipment_models_refreshed: int
    equipment_units_created: int
    equipment_units_refreshed: int
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

CATALOG_RELEASE_SMOKE_DATA = (
    CatalogReleaseSeed(
        id=UUID("20000000-0000-4000-8000-000000000001"),
        code="catalog-1",
    ),
)

EQUIPMENT_MODEL_SMOKE_DATA = (
    EquipmentModelSeed(
        id=UUID("21000000-0000-4000-8000-000000000001"),
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        code="ECS-4",
        name="Environmental Control System 4",
    ),
    EquipmentModelSeed(
        id=UUID("21000000-0000-4000-8000-000000000002"),
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        code="PWR-2",
        name="Power Regulation Unit 2",
    ),
)

EQUIPMENT_UNIT_SMOKE_DATA = (
    EquipmentUnitSeed(
        id=UUID("22000000-0000-4000-8000-000000000001"),
        facility_id=FACILITY_SMOKE_DATA[0].id,
        equipment_model_id=EQUIPMENT_MODEL_SMOKE_DATA[0].id,
        asset_tag="ECS-14",
        operational_status=EquipmentOperationalStatus.DEGRADED,
    ),
    EquipmentUnitSeed(
        id=UUID("22000000-0000-4000-8000-000000000002"),
        facility_id=FACILITY_SMOKE_DATA[1].id,
        equipment_model_id=EQUIPMENT_MODEL_SMOKE_DATA[1].id,
        asset_tag="PWR-02",
        operational_status=EquipmentOperationalStatus.OPERATIONAL,
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
              AND relation.relname IN (
                  'workspaces',
                  'facilities',
                  'catalog_releases',
                  'equipment_models',
                  'equipment_units'
              )
              AND relation.relkind = 'r'
            """
        )
    ).all()
    table_owners = {relation_name: owner for _, relation_name, owner in ownership_rows}

    expected_tables = {
        "workspaces",
        "facilities",
        "catalog_releases",
        "equipment_models",
        "equipment_units",
    }
    if set(table_owners) != expected_tables:
        raise SeedConfigurationError(
            "The workspace, Facility, and equipment migrations must be applied "
            "before seeding."
        )

    current_user = str(ownership_rows[0][0])
    if any(owner != current_user for owner in table_owners.values()):
        raise SeedConfigurationError(
            "SPACE_CORP_MIGRATION_DATABASE_URL must connect as the owner of the "
            "workspace, Facility, and equipment tables."
        )

    return current_user


def seed_smoke_data(session: Session, workspace_id: UUID) -> SeedResult:
    """Create or restore the small catalog, Facility, and unit smoke dataset."""
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

    catalog_releases_created = 0
    catalog_releases_refreshed = 0
    for seed in CATALOG_RELEASE_SMOKE_DATA:
        record = session.scalar(
            select(CatalogReleaseRecord).where(CatalogReleaseRecord.code == seed.code)
        )
        if record is None:
            record = session.get(CatalogReleaseRecord, seed.id)
            if record is not None:
                raise SeedConfigurationError(
                    f"Smoke-data catalog release ID {seed.id} has an unexpected code."
                )
        if record is None:
            record = CatalogReleaseRecord(id=seed.id)
            session.add(record)
            catalog_releases_created += 1
        elif record.id != seed.id:
            raise SeedConfigurationError(
                f"Smoke-data catalog release code {seed.code!r} has an unexpected ID."
            )
        else:
            catalog_releases_refreshed += 1

        record.code = seed.code

    session.flush()

    equipment_models_created = 0
    equipment_models_refreshed = 0
    for seed in EQUIPMENT_MODEL_SMOKE_DATA:
        record = session.scalar(
            select(EquipmentModelRecord).where(
                EquipmentModelRecord.catalog_release_id == seed.catalog_release_id,
                EquipmentModelRecord.code == seed.code,
            )
        )
        if record is None:
            record = session.get(EquipmentModelRecord, seed.id)
            if record is not None:
                raise SeedConfigurationError(
                    f"Smoke-data equipment model ID {seed.id} has an unexpected code."
                )
        if record is None:
            record = EquipmentModelRecord(id=seed.id)
            session.add(record)
            equipment_models_created += 1
        elif record.id != seed.id:
            raise SeedConfigurationError(
                f"Smoke-data equipment model code {seed.code!r} has an unexpected ID."
            )
        else:
            equipment_models_refreshed += 1

        record.catalog_release_id = seed.catalog_release_id
        record.code = seed.code
        record.name = seed.name

    session.flush()

    equipment_units_created = 0
    equipment_units_refreshed = 0
    for seed in EQUIPMENT_UNIT_SMOKE_DATA:
        record = session.scalar(
            select(EquipmentUnitRecord).where(
                EquipmentUnitRecord.workspace_id == workspace_id,
                EquipmentUnitRecord.asset_tag == seed.asset_tag,
            )
        )
        if record is None:
            record = session.get(EquipmentUnitRecord, seed.id)
            if record is not None and record.workspace_id != workspace_id:
                raise SeedConfigurationError(
                    f"Smoke-data equipment unit ID {seed.id} belongs to another workspace."
                )
        if record is None:
            record = EquipmentUnitRecord(id=seed.id, workspace_id=workspace_id)
            session.add(record)
            equipment_units_created += 1
        else:
            equipment_units_refreshed += 1

        record.facility_id = seed.facility_id
        record.equipment_model_id = seed.equipment_model_id
        record.asset_tag = seed.asset_tag
        record.operational_status = seed.operational_status.value

    session.flush()
    return SeedResult(
        workspace_id=workspace_id,
        workspace_created=workspace_created,
        catalog_releases_created=catalog_releases_created,
        catalog_releases_refreshed=catalog_releases_refreshed,
        equipment_models_created=equipment_models_created,
        equipment_models_refreshed=equipment_models_refreshed,
        equipment_units_created=equipment_units_created,
        equipment_units_refreshed=equipment_units_refreshed,
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
        f"{result.catalog_releases_created} catalog releases created and "
        f"{result.catalog_releases_refreshed} refreshed; "
        f"{result.equipment_models_created} equipment models created and "
        f"{result.equipment_models_refreshed} refreshed; "
        f"{result.equipment_units_created} equipment units created and "
        f"{result.equipment_units_refreshed} refreshed; "
        f"{result.facilities_created} Facilities created and "
        f"{result.facilities_refreshed} refreshed."
    )


if __name__ == "__main__":
    main()
