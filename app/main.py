from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException

from app.api.errors import database_unavailable, http_problem
from app.api.routes import facilities, health
from app.config import Settings
from app.database import Database, create_database


class ApplicationStartupError(RuntimeError):
    """Raised when the application cannot safely begin serving requests."""


def _validate_startup_configuration(
    settings: Settings, database: Database | None
) -> None:
    """Require the configuration needed by the currently available API."""
    if database is None and settings.database_url is None:
        raise ApplicationStartupError(
            "SPACE_CORP_DATABASE_URL must be configured before starting the application."
        )

    if settings.default_workspace_id is None:
        raise ApplicationStartupError(
            "SPACE_CORP_DEFAULT_WORKSPACE_ID must be configured before starting the application."
        )


def _verify_database_connection(database: Database) -> None:
    """Confirm the configured database is reachable before accepting requests."""
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as error:
        raise ApplicationStartupError(
            "The configured application database is unavailable."
        ) from error


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create and dispose application-owned database resources."""
    settings: Settings = application.state.settings
    database: Database | None = application.state.database

    _validate_startup_configuration(settings, database)

    if database is None:
        database = create_database(settings)
        application.state.database = database
        application.state.manages_database = True

    _verify_database_connection(database)

    try:
        yield
    finally:
        if application.state.manages_database:
            application.state.database.dispose()
            application.state.database = None


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
) -> FastAPI:
    """Create and assemble the HTTP application."""
    configured_settings = settings or Settings()
    application = FastAPI(
        title=configured_settings.application_name,
        lifespan=lifespan,
    )
    application.state.settings = configured_settings
    application.state.database = database
    application.state.manages_database = False
    application.add_exception_handler(HTTPException, http_problem)
    application.add_exception_handler(OperationalError, database_unavailable)
    application.include_router(health.router)
    application.include_router(facilities.router)

    return application


app = create_app()
