import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.database import Database
from scripts.test_environment import apply_test_environment

TEST_APPLICATION_DATABASE_URL_ENVIRONMENT_VARIABLE = "SPACE_CORP_TEST_DATABASE_URL"
TEST_MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE = "SPACE_CORP_TEST_MIGRATION_DATABASE_URL"
TEST_DATABASE_NAME_PREFIX = "space_corp_test"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
apply_test_environment()


@pytest.fixture
def integration_application_database_url(monkeypatch: pytest.MonkeyPatch) -> str:
    database_url = os.getenv(TEST_APPLICATION_DATABASE_URL_ENVIRONMENT_VARIABLE)

    if database_url is None:
        pytest.skip(f"{TEST_APPLICATION_DATABASE_URL_ENVIRONMENT_VARIABLE} is not configured.")

    database_name = make_url(database_url).database
    if database_name is None or not database_name.startswith(TEST_DATABASE_NAME_PREFIX):
        pytest.fail(
            f"{TEST_APPLICATION_DATABASE_URL_ENVIRONMENT_VARIABLE} must use a database name "
            f"starting with {TEST_DATABASE_NAME_PREFIX!r}."
        )

    monkeypatch.setenv("SPACE_CORP_DATABASE_URL", database_url)
    return database_url


@pytest.fixture
def integration_migration_database_url(monkeypatch: pytest.MonkeyPatch) -> str:
    database_url = os.getenv(TEST_MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE)

    if database_url is None:
        pytest.skip(f"{TEST_MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE} is not configured.")

    database_name = make_url(database_url).database
    if database_name is None or not database_name.startswith(TEST_DATABASE_NAME_PREFIX):
        pytest.fail(
            f"{TEST_MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE} must use a database "
            f"name starting with {TEST_DATABASE_NAME_PREFIX!r}."
        )

    monkeypatch.setenv("SPACE_CORP_MIGRATION_DATABASE_URL", database_url)
    return database_url


@pytest.fixture
def migrated_database(integration_migration_database_url: str) -> str:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    return integration_migration_database_url


@pytest.fixture
def integration_session(migrated_database: str) -> Iterator[Session]:
    database = Database(migrated_database)
    session = database.session_factory()
    transaction = session.begin()

    try:
        yield session
    finally:
        if transaction.is_active:
            transaction.rollback()
        session.close()
        database.dispose()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-integration",
        action="store_true",
        help="Require database configuration, server binaries, and zero skipped tests.",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    if session.config.getoption("--require-integration"):
        from scripts.test_environment import require_integration_environment

        try:
            require_integration_environment()
        except ValueError as error:
            raise pytest.UsageError(str(error)) from error


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if session.config.getoption("--require-integration"):
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None and reporter.stats.get("skipped"):
            reporter.write_sep("!", "Required integration run contained skipped tests")
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
