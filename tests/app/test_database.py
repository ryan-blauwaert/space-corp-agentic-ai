from pathlib import Path
from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import (
    Database,
    DatabaseConfigurationError,
    create_database,
    create_database_engine,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_create_database_engine_uses_psycopg_driver() -> None:
    engine = create_database_engine("postgresql://localhost/space_corp_test")

    try:
        assert isinstance(engine, Engine)
        assert engine.url.drivername == "postgresql+psycopg"
    finally:
        engine.dispose()


def test_create_database_engine_rejects_unsupported_postgresql_driver() -> None:
    with pytest.raises(DatabaseConfigurationError, match="Psycopg driver"):
        create_database_engine("postgresql+asyncpg://localhost/space_corp_test")


def test_database_creates_sessions_without_connecting() -> None:
    database = Database("postgresql://localhost/space_corp_test")

    try:
        with database.session() as session:
            assert session.bind is database.engine
    finally:
        database.dispose()


def test_database_session_commits_and_closes_on_success() -> None:
    database = Database("postgresql://localhost/space_corp_test")
    session = Mock(spec=Session)
    database.session_factory = Mock(return_value=session)

    try:
        with database.session() as returned_session:
            assert returned_session is session

        session.commit.assert_called_once_with()
        session.rollback.assert_not_called()
        session.close.assert_called_once_with()
    finally:
        database.dispose()


def test_database_session_rolls_back_and_closes_on_failure() -> None:
    database = Database("postgresql://localhost/space_corp_test")
    session = Mock(spec=Session)
    database.session_factory = Mock(return_value=session)

    try:
        with pytest.raises(ValueError, match="test failure"):
            with database.session():
                raise ValueError("test failure")

        session.commit.assert_not_called()
        session.rollback.assert_called_once_with()
        session.close.assert_called_once_with()
    finally:
        database.dispose()


def test_create_database_requires_configured_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPACE_CORP_DATABASE_URL", raising=False)

    with pytest.raises(DatabaseConfigurationError, match="SPACE_CORP_DATABASE_URL"):
        create_database(Settings())


@pytest.mark.integration
def test_postgresql_connection(integration_database_url: str) -> None:
    engine = create_database_engine(integration_database_url)

    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


@pytest.mark.integration
def test_migrations_apply(integration_database_url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_database_engine(integration_database_url)

    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert revision == "0002_workspace_and_facility"
    finally:
        engine.dispose()


@pytest.mark.integration
def test_migrations_match_persistence_models(integration_database_url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    command.check(config)


@pytest.mark.integration
def test_workspace_and_facility_migration_downgrades_and_reapplies(
    integration_database_url: str,
) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    try:
        command.downgrade(config, "0001_initial")
        engine = create_database_engine(integration_database_url)

        try:
            with engine.connect() as connection:
                workspace_table, facility_table = connection.execute(
                    text(
                        "SELECT to_regclass('public.workspaces'), "
                        "to_regclass('public.facilities')"
                    )
                ).one()

            assert workspace_table is None
            assert facility_table is None
        finally:
            engine.dispose()
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
def test_workspace_and_facility_tables_exist(integration_database_url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_database_engine(integration_database_url)

    try:
        with engine.connect() as connection:
            table_names = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN ('workspaces', 'facilities')"
                    )
                ).scalars()
            )

        assert table_names == {"workspaces", "facilities"}
    finally:
        engine.dispose()
