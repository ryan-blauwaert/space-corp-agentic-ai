"""Load ignored local configuration for PostgreSQL integration tests."""

import os
from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ENVIRONMENT_FILE = PROJECT_ROOT / ".env.test"


class IntegrationTestSettings(BaseSettings):
    """Local configuration for PostgreSQL integration and provisioning tests."""

    model_config = SettingsConfigDict(
        env_prefix="SPACE_CORP_TEST_",
        env_file=TEST_ENVIRONMENT_FILE,
        env_file_encoding="utf-8",
    )

    database_url: PostgresDsn | None = None
    migration_database_url: PostgresDsn | None = None
    postgres_bin: Path | None = None


def apply_test_environment(env_file: Path = TEST_ENVIRONMENT_FILE) -> None:
    """Load local test settings without overriding exported variables."""
    settings = IntegrationTestSettings(_env_file=env_file)
    values = {
        "SPACE_CORP_TEST_DATABASE_URL": settings.database_url,
        "SPACE_CORP_TEST_MIGRATION_DATABASE_URL": settings.migration_database_url,
        "SPACE_CORP_TEST_POSTGRES_BIN": settings.postgres_bin,
    }
    for variable_name, value in values.items():
        if value is not None:
            os.environ.setdefault(variable_name, str(value))
