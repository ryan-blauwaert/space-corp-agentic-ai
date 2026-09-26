"""Internal question-to-answer composition; only query planning calls the model."""

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.answers.contracts import AnswerRequest, AnswerResponse, AnswerTurn, CautiousAnswer
from app.answers.rendering import render_answer
from app.queries.contracts import QueryContext, QueryPageRequest, QueryPlan
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.service import QueryService

logger = logging.getLogger(__name__)
RENDERER_VERSION = "2"


@contextmanager
def _trace(context: QueryContext, synthesis_id: UUID, event: str) -> Iterator[dict[str, Any]]:
    started = time.monotonic()
    fields: dict[str, Any] = {"outcome": "completed", "error_kind": None}
    try:
        yield fields
    except Exception as error:
        fields.update(
            outcome="failed",
            error_kind=(
                error.kind.value
                if isinstance(error, QueryError)
                else "invalid_answer"
                if isinstance(error, ValidationError)
                else "internal_error"
            ),
        )
        raise
    finally:
        logger.info(
            json.dumps(
                {
                    "event": event,
                    "request_id": str(context.request_id),
                    "operation_id": str(synthesis_id),
                    "query_operation_id": str(context.operation_id),
                    "renderer_version": RENDERER_VERSION,
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                    **fields,
                },
                separators=(",", ":"),
            )
        )


class AnswerService:
    """Reuse existing query authority, execution limits, and provider lifetime.

    No fact-ordering call, rendering retries, database reads, or prose fallback.
    Query errors propagate unchanged; they must not become a no-results answer.
    """

    def __init__(self, queries: QueryService) -> None:
        self.queries = queries

    def ask(
        self, context: QueryContext, question: str, page: QueryPageRequest | None = None
    ) -> AnswerTurn:
        context = QueryContext.model_validate(context.model_dump(warnings=False))
        synthesis_id = uuid4()
        with _trace(context, synthesis_id, "answer_operation") as trace:
            query = self.queries.ask(context, question, page)
            if query.context != context:
                raise QueryError(context, QueryErrorKind.INVALID_PLAN)
            turn = self._render(AnswerRequest(question=question, query=query), synthesis_id)
            self._record_outcome(trace, turn)
            return turn

    def confirm_scope(
        self, context: QueryContext, pending: AnswerTurn, approved_plan: QueryPlan
    ) -> AnswerTurn:
        context = QueryContext.model_validate(context.model_dump(warnings=False))
        synthesis_id = uuid4()
        with _trace(context, synthesis_id, "answer_operation") as trace:
            try:
                pending = AnswerTurn.model_validate(pending.model_dump(warnings=False))
                outcome = pending.response.outcome
                if (
                    pending.response.context != context
                    or not isinstance(outcome, CautiousAnswer)
                    or outcome.reason != "awaiting_confirmation"
                    or pending.request.query.scope_status != "awaiting_confirmation"
                ):
                    raise ValueError("Only a pending answer in this context can be confirmed")
            except (ValueError, ValidationError):
                raise QueryError(context, QueryErrorKind.INVALID_PLAN) from None
            trace["previous_synthesis_operation_id"] = str(pending.response.synthesis_operation_id)
            query = self.queries.confirm_scope(context, pending.request.query, approved_plan)
            if query.context != context:
                raise QueryError(context, QueryErrorKind.INVALID_PLAN)
            turn = self._render(
                AnswerRequest(question=pending.request.question, query=query), synthesis_id
            )
            self._record_outcome(trace, turn)
            return turn

    def _render(self, request: AnswerRequest, synthesis_id: UUID) -> AnswerTurn:
        context = request.query.context
        with _trace(context, synthesis_id, "answer_render") as trace:
            # No selection input: deterministic rendering preserves the returned order.
            outcome = render_answer(request)
            turn = AnswerTurn(
                request=request,
                response=AnswerResponse(
                    context=context,
                    synthesis_operation_id=synthesis_id,
                    outcome=outcome,
                ),
            )
            self._record_outcome(trace, turn)
            return turn

    @staticmethod
    def _record_outcome(trace: dict[str, Any], turn: AnswerTurn) -> None:
        query, outcome = turn.request.query, turn.response.outcome
        trace.update(
            planning_operation_id=str(query.planning_operation_id),
            resolution_operation_id=str(query.resolution_operation_id),
            operation=query.plan.operation,
            scope_status=query.scope_status,
            answer_status=outcome.status,
        )
        if query.response is not None:
            trace.update(
                rows=len(query.response.result.page.rows), total=query.response.result.page.total
            )
        if isinstance(outcome, CautiousAnswer):
            trace.update(outcome="cautious", reason=outcome.reason)
        else:
            trace.update(coverage=outcome.coverage, references=len(outcome.answer.references))
