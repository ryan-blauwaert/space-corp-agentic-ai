from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Database
from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
)
from app.operations.models import IncidentRecord, WorkOrderRecord
from app.facilities.models import FacilityRecord
from scripts.seed_development_data import (
    CATALOG_RELEASE_SMOKE_DATA,
    COMPONENT_SMOKE_DATA,
    EQUIPMENT_MODEL_COMPONENT_SMOKE_DATA,
    EQUIPMENT_MODEL_SMOKE_DATA,
    EQUIPMENT_UNIT_SMOKE_DATA,
    FACILITY_SMOKE_DATA,
    INVENTORY_ITEM_SMOKE_DATA,
    INCIDENT_SMOKE_DATA,
    WORK_ORDER_SMOKE_DATA,
    SeedConfigurationError,
    require_migration_owner,
    seed_configured_development_database,
    seed_smoke_data,
)


def test_seed_requires_migration_database_url() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        default_workspace_id=uuid4(),
    )

    with pytest.raises(SeedConfigurationError, match="MIGRATION_DATABASE_URL"):
        seed_configured_development_database(settings)


def test_seed_rejects_non_development_environment() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        migration_database_url="postgresql://localhost/space_corp",
        default_workspace_id=uuid4(),
    )

    with pytest.raises(SeedConfigurationError, match="ENVIRONMENT=development"):
        seed_configured_development_database(settings)


def test_seed_rejects_test_database() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        migration_database_url="postgresql://localhost/space_corp_test",
        default_workspace_id=uuid4(),
    )

    with pytest.raises(SeedConfigurationError, match="test database"):
        seed_configured_development_database(settings)


@pytest.mark.integration
def test_seed_is_repeatable_and_scoped_to_the_selected_workspace(
    integration_session: Session,
) -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()

    first_result = seed_smoke_data(integration_session, workspace_id)
    second_result = seed_smoke_data(integration_session, workspace_id)

    assert first_result.workspace_created is True
    assert first_result.catalog_releases_created == len(CATALOG_RELEASE_SMOKE_DATA)
    assert first_result.equipment_models_created == len(EQUIPMENT_MODEL_SMOKE_DATA)
    assert first_result.components_created == len(COMPONENT_SMOKE_DATA)
    assert first_result.model_component_links_created == len(
        EQUIPMENT_MODEL_COMPONENT_SMOKE_DATA
    )
    assert first_result.equipment_units_created == len(EQUIPMENT_UNIT_SMOKE_DATA)
    assert first_result.inventory_items_created == len(INVENTORY_ITEM_SMOKE_DATA)
    assert first_result.incidents_created == len(INCIDENT_SMOKE_DATA)
    assert first_result.work_orders_created == len(WORK_ORDER_SMOKE_DATA)
    assert first_result.facilities_created == len(FACILITY_SMOKE_DATA)
    assert second_result.workspace_created is False
    assert second_result.catalog_releases_created == 0
    assert second_result.catalog_releases_refreshed == len(CATALOG_RELEASE_SMOKE_DATA)
    assert second_result.equipment_models_created == 0
    assert second_result.equipment_models_refreshed == len(EQUIPMENT_MODEL_SMOKE_DATA)
    assert second_result.components_created == 0
    assert second_result.components_refreshed == len(COMPONENT_SMOKE_DATA)
    assert second_result.model_component_links_created == 0
    assert second_result.model_component_links_refreshed == len(
        EQUIPMENT_MODEL_COMPONENT_SMOKE_DATA
    )
    assert second_result.equipment_units_created == 0
    assert second_result.equipment_units_refreshed == len(EQUIPMENT_UNIT_SMOKE_DATA)
    assert second_result.inventory_items_created == 0
    assert second_result.inventory_items_refreshed == len(INVENTORY_ITEM_SMOKE_DATA)
    assert second_result.incidents_created == 0
    assert second_result.incidents_refreshed == len(INCIDENT_SMOKE_DATA)
    assert second_result.work_orders_refreshed == len(WORK_ORDER_SMOKE_DATA)
    assert second_result.facilities_created == 0
    assert second_result.facilities_refreshed == len(FACILITY_SMOKE_DATA)
    assert integration_session.scalar(
        select(func.count()).where(FacilityRecord.workspace_id == workspace_id)
    ) == len(FACILITY_SMOKE_DATA)
    assert integration_session.scalar(
        select(func.count()).where(FacilityRecord.workspace_id == other_workspace_id)
    ) == 0
    assert integration_session.scalar(select(func.count()).select_from(CatalogReleaseRecord)) == len(
        CATALOG_RELEASE_SMOKE_DATA
    )
    assert integration_session.scalar(select(func.count()).select_from(EquipmentModelRecord)) == len(
        EQUIPMENT_MODEL_SMOKE_DATA
    )
    assert integration_session.scalar(select(func.count()).select_from(ComponentRecord)) == len(
        COMPONENT_SMOKE_DATA
    )
    assert integration_session.scalar(
        select(func.count()).where(EquipmentUnitRecord.workspace_id == workspace_id)
    ) == len(EQUIPMENT_UNIT_SMOKE_DATA)
    assert integration_session.scalar(
        select(func.count()).where(EquipmentUnitRecord.workspace_id == other_workspace_id)
    ) == 0
    assert integration_session.scalar(
        select(func.count()).where(InventoryItemRecord.workspace_id == workspace_id)
    ) == len(INVENTORY_ITEM_SMOKE_DATA)
    assert integration_session.scalar(
        select(func.count()).where(
            InventoryItemRecord.workspace_id == other_workspace_id
        )
    ) == 0
    assert integration_session.scalar(
        select(func.count()).where(IncidentRecord.workspace_id == workspace_id)
    ) == len(INCIDENT_SMOKE_DATA)
    assert integration_session.scalar(
        select(func.count()).where(IncidentRecord.workspace_id == other_workspace_id)
    ) == 0
    assert integration_session.scalar(
        select(func.count()).where(WorkOrderRecord.workspace_id == workspace_id)
    ) == len(WORK_ORDER_SMOKE_DATA)
    active_unit_incidents = integration_session.scalars(
        select(IncidentRecord).where(
            IncidentRecord.equipment_unit_id == EQUIPMENT_UNIT_SMOKE_DATA[0].id,
            IncidentRecord.status.in_(("open", "resolved")),
            IncidentRecord.fault_code == "AIRFLOW_LOW",
        )
    ).all()
    assert len(active_unit_incidents) == 2
    stockout = integration_session.get(
        InventoryItemRecord, INVENTORY_ITEM_SMOKE_DATA[0].id
    )
    assert stockout is not None
    assert (stockout.quantity_on_hand, stockout.reorder_point) == (0, 2)
    assert integration_session.scalar(
        select(InventoryItemRecord).where(
            InventoryItemRecord.workspace_id == workspace_id,
            InventoryItemRecord.facility_id == FACILITY_SMOKE_DATA[0].id,
            InventoryItemRecord.component_id == COMPONENT_SMOKE_DATA[1].id,
        )
    ) is None


@pytest.mark.integration
def test_seed_accepts_the_table_owner(integration_session: Session) -> None:
    assert require_migration_owner(integration_session) == "space_corp"


@pytest.mark.integration
def test_seed_rejects_the_restricted_application_role(
    integration_application_database_url: str,
) -> None:
    database = Database(integration_application_database_url)
    try:
        with database.session() as session:
            with pytest.raises(SeedConfigurationError, match="must connect as the owner"):
                require_migration_owner(session)
    finally:
        database.dispose()
