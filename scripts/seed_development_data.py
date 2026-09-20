"""Populate one local development workspace with repeatable smoke-test data."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Database
from app.equipment.domain import EquipmentOperationalStatus
from app.operations.domain import IncidentSeverity, IncidentStatus, WorkOrderPriority, WorkOrderStatus
from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
    equipment_model_components,
)
from app.operations.models import IncidentRecord, WorkOrderRecord
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
class ComponentSeed:
    id: UUID
    catalog_release_id: UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class EquipmentModelComponentSeed:
    catalog_release_id: UUID
    equipment_model_id: UUID
    component_id: UUID


@dataclass(frozen=True, slots=True)
class EquipmentUnitSeed:
    id: UUID
    facility_id: UUID
    equipment_model_id: UUID
    asset_tag: str
    operational_status: EquipmentOperationalStatus


@dataclass(frozen=True, slots=True)
class InventoryItemSeed:
    id: UUID
    facility_id: UUID
    component_id: UUID
    quantity_on_hand: int
    reorder_point: int


@dataclass(frozen=True, slots=True)
class IncidentSeed:
    id: UUID
    facility_id: UUID
    equipment_unit_id: UUID | None
    reference_code: str
    severity: IncidentSeverity
    status: IncidentStatus
    occurred_at: datetime
    fault_code: str | None
    resolved_at: datetime | None


@dataclass(frozen=True, slots=True)
class WorkOrderSeed:
    id: UUID
    facility_id: UUID
    originating_incident_id: UUID | None
    target_equipment_unit_id: UUID | None
    reference_code: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    due_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class SeedResult:
    workspace_id: UUID
    workspace_created: bool
    catalog_releases_created: int
    catalog_releases_refreshed: int
    equipment_models_created: int
    equipment_models_refreshed: int
    components_created: int
    components_refreshed: int
    model_component_links_created: int
    model_component_links_refreshed: int
    equipment_units_created: int
    equipment_units_refreshed: int
    inventory_items_created: int
    inventory_items_refreshed: int
    incidents_created: int
    incidents_refreshed: int
    work_orders_created: int
    work_orders_refreshed: int
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

COMPONENT_SMOKE_DATA = (
    ComponentSeed(
        id=UUID("23000000-0000-4000-8000-000000000001"),
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        code="FLT-F12",
        name="Air Filter F-12",
    ),
    ComponentSeed(
        id=UUID("23000000-0000-4000-8000-000000000002"),
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        code="SEN-THM-2",
        name="Thermal Sensor 2",
    ),
    ComponentSeed(
        id=UUID("23000000-0000-4000-8000-000000000003"),
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        code="PWR-FUS-5",
        name="Power Fuse 5",
    ),
)

EQUIPMENT_MODEL_COMPONENT_SMOKE_DATA = (
    EquipmentModelComponentSeed(
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        equipment_model_id=EQUIPMENT_MODEL_SMOKE_DATA[0].id,
        component_id=COMPONENT_SMOKE_DATA[0].id,
    ),
    EquipmentModelComponentSeed(
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        equipment_model_id=EQUIPMENT_MODEL_SMOKE_DATA[0].id,
        component_id=COMPONENT_SMOKE_DATA[1].id,
    ),
    EquipmentModelComponentSeed(
        catalog_release_id=CATALOG_RELEASE_SMOKE_DATA[0].id,
        equipment_model_id=EQUIPMENT_MODEL_SMOKE_DATA[1].id,
        component_id=COMPONENT_SMOKE_DATA[2].id,
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

INVENTORY_ITEM_SMOKE_DATA = (
    InventoryItemSeed(
        id=UUID("24000000-0000-4000-8000-000000000001"),
        facility_id=FACILITY_SMOKE_DATA[0].id,
        component_id=COMPONENT_SMOKE_DATA[0].id,
        quantity_on_hand=0,
        reorder_point=2,
    ),
    InventoryItemSeed(
        id=UUID("24000000-0000-4000-8000-000000000002"),
        facility_id=FACILITY_SMOKE_DATA[1].id,
        component_id=COMPONENT_SMOKE_DATA[2].id,
        quantity_on_hand=2,
        reorder_point=3,
    ),
    InventoryItemSeed(
        id=UUID("24000000-0000-4000-8000-000000000003"),
        facility_id=FACILITY_SMOKE_DATA[2].id,
        component_id=COMPONENT_SMOKE_DATA[1].id,
        quantity_on_hand=5,
        reorder_point=5,
    ),
)

INCIDENT_SMOKE_DATA = (
    IncidentSeed(
        id=UUID("25000000-0000-4000-8000-000000000001"),
        facility_id=FACILITY_SMOKE_DATA[0].id,
        equipment_unit_id=EQUIPMENT_UNIT_SMOKE_DATA[0].id,
        reference_code="INC-ECS-001",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        occurred_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        fault_code="AIRFLOW_LOW",
        resolved_at=None,
    ),
    IncidentSeed(
        id=UUID("25000000-0000-4000-8000-000000000002"),
        facility_id=FACILITY_SMOKE_DATA[0].id,
        equipment_unit_id=EQUIPMENT_UNIT_SMOKE_DATA[0].id,
        reference_code="INC-ECS-002",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.RESOLVED,
        occurred_at=datetime(2025, 12, 1, 8, 0, tzinfo=UTC),
        fault_code="AIRFLOW_LOW",
        resolved_at=datetime(2025, 12, 1, 10, 0, tzinfo=UTC),
    ),
    IncidentSeed(
        id=UUID("25000000-0000-4000-8000-000000000003"),
        facility_id=FACILITY_SMOKE_DATA[0].id,
        equipment_unit_id=None,
        reference_code="INC-LUN-001",
        severity=IncidentSeverity.LOW,
        status=IncidentStatus.INVESTIGATING,
        occurred_at=datetime(2026, 1, 16, 9, 0, tzinfo=UTC),
        fault_code=None,
        resolved_at=None,
    ),
)

WORK_ORDER_SMOKE_DATA = (
    WorkOrderSeed(UUID("26000000-0000-4000-8000-000000000001"), FACILITY_SMOKE_DATA[0].id, INCIDENT_SMOKE_DATA[0].id, EQUIPMENT_UNIT_SMOKE_DATA[0].id, "WO-ECS-001", WorkOrderPriority.CRITICAL, WorkOrderStatus.BLOCKED, datetime(2026, 1, 20, 12, 0, tzinfo=UTC), None),
    WorkOrderSeed(UUID("26000000-0000-4000-8000-000000000002"), FACILITY_SMOKE_DATA[0].id, None, None, "WO-LUN-001", WorkOrderPriority.HIGH, WorkOrderStatus.OPEN, None, None),
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
                  'components',
                  'equipment_model_components',
                  'equipment_units',
                  'inventory_items',
                  'incidents'
                  ,'work_orders'
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
        "components",
        "equipment_model_components",
        "equipment_units",
        "inventory_items",
        "incidents",
        "work_orders",
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
    """Create or restore the small catalog, Facility, unit, inventory, and incident dataset."""
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

    components_created = 0
    components_refreshed = 0
    for seed in COMPONENT_SMOKE_DATA:
        record = session.scalar(
            select(ComponentRecord).where(
                ComponentRecord.catalog_release_id == seed.catalog_release_id,
                ComponentRecord.code == seed.code,
            )
        )
        if record is None:
            record = session.get(ComponentRecord, seed.id)
            if record is not None:
                raise SeedConfigurationError(
                    f"Smoke-data component ID {seed.id} has an unexpected code."
                )
        if record is None:
            record = ComponentRecord(id=seed.id)
            session.add(record)
            components_created += 1
        elif record.id != seed.id:
            raise SeedConfigurationError(
                f"Smoke-data component code {seed.code!r} has an unexpected ID."
            )
        else:
            components_refreshed += 1

        record.catalog_release_id = seed.catalog_release_id
        record.code = seed.code
        record.name = seed.name

    session.flush()

    model_component_links_created = 0
    model_component_links_refreshed = 0
    for seed in EQUIPMENT_MODEL_COMPONENT_SMOKE_DATA:
        exists = session.execute(
            select(equipment_model_components.c.equipment_model_id).where(
                equipment_model_components.c.catalog_release_id
                == seed.catalog_release_id,
                equipment_model_components.c.equipment_model_id
                == seed.equipment_model_id,
                equipment_model_components.c.component_id == seed.component_id,
            )
        ).first()
        if exists is None:
            session.execute(
                equipment_model_components.insert().values(
                    catalog_release_id=seed.catalog_release_id,
                    equipment_model_id=seed.equipment_model_id,
                    component_id=seed.component_id,
                )
            )
            model_component_links_created += 1
        else:
            model_component_links_refreshed += 1

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
    inventory_items_created = 0
    inventory_items_refreshed = 0
    for seed in INVENTORY_ITEM_SMOKE_DATA:
        record = session.scalar(
            select(InventoryItemRecord).where(
                InventoryItemRecord.workspace_id == workspace_id,
                InventoryItemRecord.facility_id == seed.facility_id,
                InventoryItemRecord.component_id == seed.component_id,
            )
        )
        if record is None:
            record = session.get(InventoryItemRecord, seed.id)
            if record is not None and record.workspace_id != workspace_id:
                raise SeedConfigurationError(
                    f"Smoke-data inventory ID {seed.id} belongs to another workspace."
                )
        if record is None:
            record = InventoryItemRecord(id=seed.id, workspace_id=workspace_id)
            session.add(record)
            inventory_items_created += 1
        else:
            inventory_items_refreshed += 1

        record.facility_id = seed.facility_id
        record.component_id = seed.component_id
        record.quantity_on_hand = seed.quantity_on_hand
        record.reorder_point = seed.reorder_point

    session.flush()
    incidents_created = 0
    incidents_refreshed = 0
    for seed in INCIDENT_SMOKE_DATA:
        record = session.scalar(
            select(IncidentRecord).where(
                IncidentRecord.workspace_id == workspace_id,
                IncidentRecord.reference_code == seed.reference_code,
            )
        )
        if record is None:
            record = session.get(IncidentRecord, seed.id)
            if record is not None and record.workspace_id != workspace_id:
                raise SeedConfigurationError(
                    f"Smoke-data incident ID {seed.id} belongs to another workspace."
                )
        if record is None:
            record = IncidentRecord(id=seed.id, workspace_id=workspace_id)
            session.add(record)
            incidents_created += 1
        else:
            incidents_refreshed += 1

        record.facility_id = seed.facility_id
        record.equipment_unit_id = seed.equipment_unit_id
        record.reference_code = seed.reference_code
        record.severity = seed.severity.value
        record.status = seed.status.value
        record.occurred_at = seed.occurred_at
        record.fault_code = seed.fault_code
        record.resolved_at = seed.resolved_at

    session.flush()
    work_orders_created = 0
    work_orders_refreshed = 0
    for seed in WORK_ORDER_SMOKE_DATA:
        record = session.scalar(select(WorkOrderRecord).where(WorkOrderRecord.workspace_id == workspace_id, WorkOrderRecord.reference_code == seed.reference_code))
        if record is None:
            record = WorkOrderRecord(id=seed.id, workspace_id=workspace_id)
            session.add(record)
            work_orders_created += 1
        else:
            work_orders_refreshed += 1
        record.facility_id = seed.facility_id
        record.originating_incident_id = seed.originating_incident_id
        record.target_equipment_unit_id = seed.target_equipment_unit_id
        record.reference_code = seed.reference_code
        record.priority = seed.priority.value
        record.status = seed.status.value
        record.due_at = seed.due_at
        record.completed_at = seed.completed_at

    session.flush()
    return SeedResult(
        workspace_id=workspace_id,
        workspace_created=workspace_created,
        catalog_releases_created=catalog_releases_created,
        catalog_releases_refreshed=catalog_releases_refreshed,
        equipment_models_created=equipment_models_created,
        equipment_models_refreshed=equipment_models_refreshed,
        components_created=components_created,
        components_refreshed=components_refreshed,
        model_component_links_created=model_component_links_created,
        model_component_links_refreshed=model_component_links_refreshed,
        equipment_units_created=equipment_units_created,
        equipment_units_refreshed=equipment_units_refreshed,
        inventory_items_created=inventory_items_created,
        inventory_items_refreshed=inventory_items_refreshed,
        incidents_created=incidents_created,
        incidents_refreshed=incidents_refreshed,
        work_orders_created=work_orders_created,
        work_orders_refreshed=work_orders_refreshed,
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
        f"{result.components_created} components created and "
        f"{result.components_refreshed} refreshed; "
        f"{result.model_component_links_created} model-component links created and "
        f"{result.model_component_links_refreshed} refreshed; "
        f"{result.equipment_units_created} equipment units created and "
        f"{result.equipment_units_refreshed} refreshed; "
        f"{result.inventory_items_created} inventory items created and "
        f"{result.inventory_items_refreshed} refreshed; "
        f"{result.incidents_created} incidents created and "
        f"{result.incidents_refreshed} refreshed; "
        f"{result.facilities_created} Facilities created and "
        f"{result.facilities_refreshed} refreshed."
    )


if __name__ == "__main__":
    main()
