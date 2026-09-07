from alembic import context

from app.config import Settings
from app.database import DatabaseConfigurationError, create_database_engine
from app.facilities.models import FacilityRecord  # noqa: F401
from app.persistence.base import Base
from app.workspaces.models import WorkspaceRecord  # noqa: F401


config = context.config
target_metadata = Base.metadata


def migration_database_url() -> str:
    settings = Settings()

    if settings.migration_database_url is None:
        raise DatabaseConfigurationError(
            "SPACE_CORP_MIGRATION_DATABASE_URL must be configured before running "
            "migrations."
        )

    return str(settings.migration_database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=migration_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_database_engine(migration_database_url())

    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
