"""Public question contracts; clients never supply execution authority or evidence."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.answers.contracts import AnswerOutcome
from app.queries.contracts import Frozen, PlanningOutcome, QueryPageRequest, QueryResult

ConfirmationId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]


class QuestionRequest(Frozen):
    question: str = Field(min_length=1, max_length=4000, pattern=r"\S", repr=False)
    page: QueryPageRequest = Field(default_factory=QueryPageRequest)


class ConfirmationRequest(Frozen):
    confirmation_id: ConfirmationId = Field(repr=False)


class PendingConfirmation(Frozen):
    confirmation_id: ConfirmationId = Field(repr=False)
    expires_in_seconds: int


class QuestionResponse(Frozen):
    request_id: UUID
    query_operation_id: UUID
    synthesis_operation_id: UUID
    outcome: AnswerOutcome
    plan: PlanningOutcome
    scope_status: Literal["not_required", "awaiting_confirmation", "confirmed"]
    page: QueryPageRequest
    evidence: QueryResult | None
    confirmation: PendingConfirmation | None = None
