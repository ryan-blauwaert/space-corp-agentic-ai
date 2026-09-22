"""Answer values, not proof of grounding or permission to execute a query."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, TypeAdapter, model_validator

from app.queries.contracts import (
    CompatibleStockEvidence,
    DeclinedPlan,
    FacilityEquipmentEvidence,
    Frozen,
    IncidentEvidence,
    InventoryEvidence,
    QueryContext,
    WorkOrderEvidence,
)
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


FactId = Annotated[str, Field(pattern=r"^[0-9a-f]{64}:[0-9]+$")]


class FacilityFact(Frozen):
    kind: Literal["facility_equipment"] = "facility_equipment"
    fact_id: FactId
    evidence: FacilityEquipmentEvidence = Field(repr=False)


class StockFact(Frozen):
    kind: Literal["compatible_stock"] = "compatible_stock"
    fact_id: FactId
    evidence: CompatibleStockEvidence = Field(repr=False)


class WorkOrderFact(Frozen):
    kind: Literal["work_orders"] = "work_orders"
    fact_id: FactId
    evidence: WorkOrderEvidence = Field(repr=False)


class IncidentFact(Frozen):
    kind: Literal["incidents"] = "incidents"
    fact_id: FactId
    evidence: IncidentEvidence = Field(repr=False)


class InventoryFact(Frozen):
    kind: Literal["inventory"] = "inventory"
    fact_id: FactId
    evidence: InventoryEvidence = Field(repr=False)


EvidenceFact = Annotated[
    FacilityFact | StockFact | WorkOrderFact | IncidentFact | InventoryFact,
    Field(discriminator="kind"),
]


class FactSelection(Frozen):
    """Untrusted presentation preference only; never facts, text, or authority.

    Listed facts appear first. All other returned facts remain in the answer.
    """

    fact_ids: tuple[FactId, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_facts(self) -> "FactSelection":
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError("Selected facts must be unique")
        return self


class RenderedAnswer(Frozen):
    """Application output only. The renderer never accepts this as input."""

    text: AnswerText = Field(repr=False)
    references: tuple[RecordReference, ...] = Field(max_length=500)


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
    answer: RenderedAnswer = Field(repr=False)
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


class AnswerTurn(Frozen):
    """Internal result retaining the original question and pending/executed query.

    Not a persisted session or an HTTP approval token. Only a trusted caller may
    retain this value and submit it for exact-plan scope confirmation.
    """

    request: AnswerRequest = Field(repr=False)
    response: AnswerResponse = Field(repr=False)

    @model_validator(mode="after")
    def consistent_context(self) -> "AnswerTurn":
        if self.request.query.context != self.response.context:
            raise ValueError("Answer and query contexts must match")
        return self
