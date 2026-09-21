"""One bounded model proposal followed by application-owned read-only execution."""

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, ValidationError

from app.database import Database
from app.llm.contracts import ModelCallContext, ModelFinishReason, ModelRequest
from app.llm.errors import ModelCallError
from app.llm.service import ModelService
from app.queries.contracts import (
    DeclinedPlan,
    Frozen,
    PlanningOutcome,
    QueryContext,
    QueryPageRequest,
    QueryResponse,
)
from app.queries.equipment import EquipmentQueryExecutor
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.operations import OperationsQueryExecutor
from app.queries.planning import (
    MAX_QUESTION_LENGTH,
    PROMPT_ID,
    PROMPT_VERSION,
    parse_plan,
    planning_prompt,
)
from app.queries.resolution import ground_references, resolve_plan

logger = logging.getLogger(__name__)


class QueryOutcome(Frozen):
    context: QueryContext
    planning_operation_id: UUID
    resolution_operation_id: UUID
    returned_model_id: str | None = None
    plan: PlanningOutcome = Field(repr=False)
    response: QueryResponse | None = Field(default=None, repr=False)


@contextmanager
def _trace(context: QueryContext, operation_id: UUID, event: str) -> Iterator[dict[str, Any]]:
    started = time.monotonic()
    fields: dict[str, Any] = {"outcome": "completed", "error_kind": None}
    try:
        yield fields
    except Exception as error:
        fields.update(
            outcome="failed",
            error_kind=error.kind.value if isinstance(error, QueryError) else "internal_error",
        )
        raise
    finally:
        logger.info(
            json.dumps(
                {
                    "event": event,
                    "request_id": str(context.request_id),
                    "operation_id": str(operation_id),
                    "query_operation_id": str(context.operation_id),
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                    **fields,
                },
                separators=(",", ":"),
            )
        )


class QueryService:
    def __init__(self, database: Database, model: ModelService, model_id: str) -> None:
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be nonblank")
        self.database = database
        self.model = model
        self.model_id = model_id
        self.equipment = EquipmentQueryExecutor(database)
        self.operations = OperationsQueryExecutor(database)

    def ask(
        self, context: QueryContext, question: str, page: QueryPageRequest | None = None
    ) -> QueryOutcome:
        """Caller supplies authorization and pagination; model supplies neither."""
        try:
            context = QueryContext.model_validate(context.model_dump(warnings=False))
            page = QueryPageRequest.model_validate(page.model_dump(warnings=False) if page else {})
            if (
                not isinstance(question, str)
                or not question.strip()
                or len(question) > MAX_QUESTION_LENGTH
            ):
                raise ValueError("Invalid question")
        except (ValueError, ValidationError):
            raise QueryError(context, QueryErrorKind.INVALID_PLAN) from None
        with _trace(context, uuid4(), "query_grounding"):
            reference_types = ground_references(self.database, context, question)
        planning_id, resolution_id = uuid4(), uuid4()
        with _trace(context, planning_id, "query_planning") as trace:
            trace.update(model_id=self.model_id, prompt_id=PROMPT_ID, prompt_version=PROMPT_VERSION)
            try:
                result = self.model.generate(
                    ModelRequest(
                        context=ModelCallContext(
                            request_id=context.request_id,
                            operation_id=planning_id,
                            model_id=self.model_id,
                            prompt_id=PROMPT_ID,
                            prompt_version=PROMPT_VERSION,
                        ),
                        prompt=planning_prompt(
                            question,
                            datetime.now(UTC),
                            {
                                reference: list(kinds)
                                for reference, kinds in reference_types.items()
                            },
                        ),
                        max_output_tokens=4096,
                        timeout_seconds=30.0,
                    )
                )
            except ModelCallError:
                raise QueryError(context, QueryErrorKind.MODEL_FAILURE) from None
            if result.finish_reason != ModelFinishReason.COMPLETED:
                raise QueryError(context, QueryErrorKind.MODEL_FAILURE)
            proposal = parse_plan(result.text, question, context)
            trace["operation"] = proposal["operation"]
            if proposal["operation"] == "declined":
                trace["outcome"] = "declined"
        with _trace(context, resolution_id, "query_resolution") as trace:
            plan = resolve_plan(self.database, context, proposal)
            trace["operation"] = plan.operation
            if isinstance(plan, DeclinedPlan):
                trace["outcome"] = "declined"
        response = None
        if not isinstance(plan, DeclinedPlan):
            with _trace(context, context.operation_id, "query_execution") as trace:
                trace["operation"] = plan.operation
                executor = (
                    self.equipment
                    if plan.operation in ("facility_equipment", "compatible_stock")
                    else self.operations
                )
                response = executor.execute(context, plan, page)
                trace.update(total=response.result.page.total, rows=len(response.result.page.rows))
        return QueryOutcome(
            context=context,
            planning_operation_id=planning_id,
            resolution_operation_id=resolution_id,
            returned_model_id=result.returned_model_id,
            plan=plan,
            response=response,
        )
