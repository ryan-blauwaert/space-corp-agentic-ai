from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.persistence.models import (
    CatalogReleaseRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    FacilityRecord,
    WorkspaceRecord,
)


_REGISTERED_MODELS = (
    CatalogReleaseRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    FacilityRecord,
    WorkspaceRecord,
)


class DatabaseConfigurationError(RuntimeError):
    """Raised when database access is requested without a configured URL."""


class Database:
    """Owns the application database engine and creates short-lived sessions."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_database_engine(database_url)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def workspace_session(self, workspace_id: UUID) -> Iterator[Session]:
        """Create a transaction scoped to one trusted workspace for RLS."""
        with self.session() as session:
            session.execute(
                text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
                {"workspace_id": str(workspace_id)},
            )
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


def create_database(settings: Settings) -> Database:
    """Create database resources from application settings when configured."""
    if settings.database_url is None:
        raise DatabaseConfigurationError(
            "SPACE_CORP_DATABASE_URL must be configured before using the database."
        )

    return Database(str(settings.database_url))


def create_database_engine(database_url: str) -> Engine:
    """Create a PostgreSQL engine using the project's Psycopg driver."""
    url = make_url(database_url)

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise DatabaseConfigurationError(
            "SPACE_CORP_DATABASE_URL must use the PostgreSQL Psycopg driver."
        )

    return create_engine(url, pool_pre_ping=True)
