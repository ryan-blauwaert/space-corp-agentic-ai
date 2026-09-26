"""Local read-only question journey with explicit exact-plan scope confirmation."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from app.answers.contracts import AnswerTurn
from app.answers.service import AnswerService
from app.api.dependencies import get_answer_service, get_default_workspace_id, get_pending_answers
from app.api.pending_answers import PendingAnswerCapacity, PendingAnswers, PendingAnswerUnavailable
from app.queries.contracts import DeclinedPlan, QueryContext
from app.queries.errors import QueryError, QueryErrorKind
from app.schemas.problems import ProblemDetail
from app.schemas.questions import (
    ConfirmationRequest,
    PendingConfirmation,
    QuestionRequest,
    QuestionResponse,
)

ERRORS = {
    QueryErrorKind.INVALID_PLAN: (502, "The question could not be interpreted safely."),
    QueryErrorKind.NOT_FOUND: (404, "A referenced record is not available."),
    QueryErrorKind.MODEL_FAILURE: (503, "Question planning is unavailable. Please try again."),
    QueryErrorKind.DATABASE_UNAVAILABLE: (503, "The operational API database is unavailable."),
    QueryErrorKind.TIMEOUT: (504, "The query timed out. Try a narrower question."),
    QueryErrorKind.RESOURCE_LIMIT: (
        400,
        "The query exceeds execution limits. Narrow the question.",
    ),
}

router = APIRouter(
    prefix="/questions",
    tags=["questions"],
    responses={
        code: {
            "description": description,
            "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}},
        }
        for code, description in {
            404: "Referenced record or pending confirmation unavailable.",
            400: "Query exceeds execution limits.",
            500: "Unexpected question failure.",
            502: "Invalid model query proposal.",
            503: "Model, database, configuration, or pending capacity unavailable.",
            504: "Query execution timed out.",
        }.items()
    },
)


@contextmanager
def question_errors(context: QueryContext, response: Response) -> Iterator[None]:
    headers = {"X-Request-ID": str(context.request_id), "Cache-Control": "no-store"}
    response.headers.update(headers)
    try:
        yield
    except QueryError as error:
        code, detail = ERRORS[error.kind]
        raise HTTPException(code, detail, headers=headers) from None
    except PendingAnswerCapacity:
        raise HTTPException(503, "Too many pending questions. Try again later.", headers=headers)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, "The question could not be completed.", headers=headers) from None


def public_response(turn: AnswerTurn, pending: PendingAnswers) -> QuestionResponse:
    query = turn.request.query
    confirmation = None
    if query.scope_status == "awaiting_confirmation":
        confirmation = PendingConfirmation(
            confirmation_id=pending.add(turn), expires_in_seconds=pending.ttl_seconds
        )
    return QuestionResponse(
        request_id=query.context.request_id,
        query_operation_id=query.context.operation_id,
        synthesis_operation_id=turn.response.synthesis_operation_id,
        outcome=turn.response.outcome,
        plan=query.plan,
        scope_status=query.scope_status,
        page=query.page_request,
        evidence=query.response.result if query.response is not None else None,
        confirmation=confirmation,
    )


@router.post("", response_model=QuestionResponse, operation_id="askQuestion")
def ask_question(
    body: QuestionRequest,
    response: Response,
    answers: Annotated[AnswerService, Depends(get_answer_service)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    pending: Annotated[PendingAnswers, Depends(get_pending_answers)],
) -> QuestionResponse:
    """Plan one bounded question; unanchored scope returns for review without execution.

    Executed evidence includes stored display names/codes where available. Answer prose
    prefers those labels; exact UUIDs remain in evidence and record references.
    """
    context = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace_id)
    with question_errors(context, response):
        return public_response(answers.ask(context, body.question, body.page), pending)


@router.post("/confirm", response_model=QuestionResponse, operation_id="confirmQuestionScope")
def confirm_question_scope(
    body: ConfirmationRequest,
    response: Response,
    answers: Annotated[AnswerService, Depends(get_answer_service)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    pending: Annotated[PendingAnswers, Depends(get_pending_answers)],
) -> QuestionResponse:
    """Approve the exact displayed plan. Consume its handle once, without replanning."""
    try:
        turn = pending.take(body.confirmation_id, workspace_id)
    except PendingAnswerUnavailable:
        raise HTTPException(
            404,
            "Confirmation is unavailable. Submit the question again.",
            headers={"Cache-Control": "no-store"},
        ) from None
    context, plan = turn.request.query.context, turn.request.query.plan
    with question_errors(context, response):
        assert not isinstance(plan, DeclinedPlan)
        return public_response(answers.confirm_scope(context, turn, plan), pending)
