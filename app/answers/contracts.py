"""Answer values, not proof of grounding or permission to execute a query."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, StrictStr, TypeAdapter, model_validator

from app.queries.contracts import DeclinedPlan, Frozen, QueryContext
from app.queries.service import QueryOutcome

AnswerText = Annotated[str, Field(min_length=1, max_length=12000, pattern=r"\S")]


class RecordReference(Frozen):
    entity: Literal[
        "facility",
        "equipment_unit",
        "equipment_model",
        "component",
        "inventory",
        "incident",
        "work_order",
    ]
    record_id: UUID


class EvidenceClaim(Frozen):
    """An exact scalar assertion about a path in the returned QueryResult JSON.

    String segments select fields; nonnegative integer segments select list entries.
    No expressions, attribute access, aggregation, or external lookups are supported.
    """

    path: tuple[StrictStr | Annotated[int, Field(strict=True, ge=0)], ...] = Field(
        min_length=1, max_length=12
    )
    value: StrictStr | StrictInt | StrictBool | None


class AnswerDraft(Frozen):
    """Untrusted model output. Valid schema and real IDs do not prove true prose."""

    text: AnswerText = Field(repr=False)
    references: tuple[RecordReference, ...] = Field(max_length=500)
    claims: tuple[EvidenceClaim, ...] = Field(default=(), max_length=500, repr=False)

    @model_validator(mode="after")
    def unique_references(self) -> "AnswerDraft":
        if len(set(self.references)) != len(self.references):
            raise ValueError("Answer references must be unique")
        return self


class AnswerRequest(Frozen):
    """Trusted orchestration input; the model must not supply query authority."""

    question: str = Field(min_length=1, max_length=4000, pattern=r"\S", repr=False)
    query: QueryOutcome = Field(repr=False)

    @model_validator(mode="after")
    def consistent_evidence(self) -> "AnswerRequest":
        query = self.query
        if isinstance(query.plan, DeclinedPlan):
            if query.response is not None or query.scope_status != "not_required":
                raise ValueError("Declined queries cannot carry evidence or scope approval")
        elif query.scope_status == "awaiting_confirmation":
            if query.response is not None:
                raise ValueError("Pending scope must not carry executed evidence")
        elif query.response is not None:
            if query.response.context != query.context:
                raise ValueError("Query and evidence contexts must match")
            if query.response.result.operation != query.plan.operation:
                raise ValueError("Query and evidence operations must match")
        # No response for a supported plan is representable as insufficient evidence.
        return self


class Answered(Frozen):
    """Application output after validation; never accept directly from the model."""

    status: Literal["answered"] = "answered"
    answer: AnswerDraft = Field(repr=False)
    coverage: Literal["complete", "partial"]


class CautiousAnswer(Frozen):
    status: Literal["cautious"] = "cautious"
    reason: Literal[
        "no_results",
        "insufficient_evidence",
        "awaiting_confirmation",
        "declined",
        "invalid_answer",
        "model_failure",
    ]
    text: AnswerText = Field(repr=False)


AnswerOutcome = Annotated[Answered | CautiousAnswer, Field(discriminator="status")]
ANSWER_OUTCOME: TypeAdapter[AnswerOutcome] = TypeAdapter(AnswerOutcome)


class AnswerResponse(Frozen):
    context: QueryContext
    synthesis_operation_id: UUID
    outcome: AnswerOutcome = Field(repr=False)
