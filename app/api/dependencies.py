"""Dependencies shared by HTTP API routes."""

from uuid import UUID

from fastapi import HTTPException, Request, status

from app.database import Database


def get_database(request: Request) -> Database:
    """Return the application database or reject unavailable API operations."""
    database = request.app.state.database

    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The Facility API database is not configured.",
        )

    return database


def get_default_workspace_id(request: Request) -> UUID:
    """Return the server-configured local-development workspace scope."""
    workspace_id = request.app.state.settings.default_workspace_id

    if workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPACE_CORP_DEFAULT_WORKSPACE_ID must be configured.",
        )

    return workspace_id
