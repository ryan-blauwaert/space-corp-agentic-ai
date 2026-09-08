from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import facilities, health
from app.config import Settings
from app.database import Database, create_database


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create and dispose application-owned database resources."""
    settings: Settings = application.state.settings

    if application.state.database is None and settings.database_url is not None:
        application.state.database = create_database(settings)
        application.state.manages_database = True

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
    application.include_router(health.router)
    application.include_router(facilities.router)

    return application


app = create_app()
