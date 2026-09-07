from unittest.mock import Mock

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import (
    Database,
    DatabaseConfigurationError,
    create_database,
    create_database_engine,
)


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


def test_create_database_requires_configured_url() -> None:
    with pytest.raises(DatabaseConfigurationError, match="SPACE_CORP_DATABASE_URL"):
        create_database(Settings())
