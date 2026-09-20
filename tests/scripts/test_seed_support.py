import pytest
from sqlalchemy.orm import Session

from app.database import Database
from scripts.seed_support import SeedConfigurationError, require_migration_owner


@pytest.mark.integration
def test_dataset_accepts_the_table_owner(integration_session: Session) -> None:
    assert require_migration_owner(integration_session) == "space_corp"


@pytest.mark.integration
def test_dataset_rejects_the_restricted_application_role(
    integration_application_database_url: str,
) -> None:
    database = Database(integration_application_database_url)
    try:
        with database.session() as session:
            with pytest.raises(SeedConfigurationError, match="must connect as the owner"):
                require_migration_owner(session)
    finally:
        database.dispose()
