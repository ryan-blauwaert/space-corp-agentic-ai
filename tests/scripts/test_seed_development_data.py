from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Database
from app.facilities.models import FacilityRecord
from scripts.seed_development_data import (
    FACILITY_SMOKE_DATA,
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
    assert first_result.facilities_created == len(FACILITY_SMOKE_DATA)
    assert second_result.workspace_created is False
    assert second_result.facilities_created == 0
    assert second_result.facilities_refreshed == len(FACILITY_SMOKE_DATA)
    assert integration_session.scalar(
        select(func.count()).where(FacilityRecord.workspace_id == workspace_id)
    ) == len(FACILITY_SMOKE_DATA)
    assert integration_session.scalar(
        select(func.count()).where(FacilityRecord.workspace_id == other_workspace_id)
    ) == 0


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
