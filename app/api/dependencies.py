"""Dependencies shared by HTTP API routes."""

from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from app.answers.service import AnswerService
from app.api.pending_answers import PendingAnswers
from app.database import Database
from app.llm.configuration import configured_provider
from app.llm.service import ModelService
from app.queries.service import QueryService


def get_database(request: Request) -> Database:
    """Return the application database or reject unavailable API operations."""
    database = request.app.state.database

    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The operational API database is not configured.",
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


def get_pending_answers(request: Request) -> PendingAnswers:
    return request.app.state.pending_answers


def get_answer_service(
    request: Request, database: Annotated[Database, Depends(get_database)]
) -> Iterator[AnswerService]:
    """Own one provider client per HTTP request; ordinary reads need no model key."""
    settings = request.app.state.settings
    if (
        settings.llm_model_id is None
        or settings.llm_api_key is None
        or not settings.llm_api_key.get_secret_value().strip()
    ):
        raise HTTPException(503, "Question planning is not configured.")
    with configured_provider(settings) as provider:
        yield AnswerService(QueryService(database, ModelService(provider), settings.llm_model_id))
