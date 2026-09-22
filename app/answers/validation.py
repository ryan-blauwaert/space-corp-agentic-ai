"""Returned identity membership, bounded selection, and cautious responses."""

from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from app.answers.contracts import (
    AnswerRequest,
    CautiousAnswer,
    FactSelection,
    RecordReference,
)
from app.queries.contracts import DeclinedPlan, QueryResult
from app.queries.service import needs_scope_confirmation

# The evidence contracts use these explicit identity fields, including nested evidence.
_IDENTITIES: dict[
    str,
    Literal[
        "facility",
        "equipment_unit",
        "equipment_model",
        "component",
        "inventory",
        "incident",
        "work_order",
    ],
] = {
    "facility_id": "facility",
    "unit_id": "equipment_unit",
    "equipment_unit_id": "equipment_unit",
    "model_id": "equipment_model",
    "component_id": "component",
    "inventory_id": "inventory",
    "incident_id": "incident",
    "incident_ids": "incident",
    "work_order_id": "work_order",
    "originating_incident_id": "incident",
    "incident_equipment_unit_id": "equipment_unit",
    "target_equipment_unit_id": "equipment_unit",
}


def evidence_references(result: QueryResult) -> frozenset[RecordReference]:
    """Only returned result identifiers count, never plan/question/context IDs."""
    found: set[RecordReference] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _IDENTITIES and item is not None:
                    for identity in item if isinstance(item, list) else [item]:
                        found.add(
                            RecordReference(entity=_IDENTITIES[key], record_id=UUID(identity))
                        )
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result.model_dump(mode="json"))
    return frozenset(found)


def cautious_response(request: AnswerRequest) -> CautiousAnswer | None:
    """Return a deterministic pre-generation response when evidence cannot answer."""
    request = AnswerRequest.model_validate(request.model_dump(warnings=False))
    query = request.query
    if isinstance(query.plan, DeclinedPlan):
        messages = {
            "missing_input": "Please provide the missing reference or scope before I can query records.",
            "ambiguous_input": "Please clarify which record or scope you mean before I query records.",
            "unsupported_question": "This question is outside the supported operational query capabilities.",
            "prohibited_operation": "This read-only query flow cannot perform the requested operation or bypass workspace access controls.",
        }
        return CautiousAnswer(reason="declined", text=messages[query.plan.reason])
    if query.scope_status == "awaiting_confirmation" or (
        needs_scope_confirmation(query.plan) and query.scope_status != "confirmed"
    ):
        return CautiousAnswer(
            reason="awaiting_confirmation",
            text="Please review and confirm the proposed query scope before records are retrieved.",
        )
    if query.response is None:
        return CautiousAnswer(
            reason="insufficient_evidence",
            text="No executed query evidence is available to answer this question.",
        )
    result = query.response.result
    if result.page.total == 0:
        text = "No records matched the requested query scope and filters."
        if result.operation == "compatible_stock":
            if result.status == "no_incident_match":
                text = "No incident matched the requested condition, so this conditional query returned no compatible components."
            elif result.status == "no_compatibility":
                text = "No compatible components were returned for this query."
                if result.incident_ids:
                    text += " Matching incidents were returned."
                text += " This does not establish whether components are in stock."
        return CautiousAnswer(reason="no_results", text=text)
    if not result.page.rows:
        return CautiousAnswer(
            reason="insufficient_evidence",
            text=f"The query matched {result.page.total} records, but this page contains none. Record details cannot be answered from this page.",
        )
    return None


def failed_answer(reason: Literal["invalid_answer", "model_failure"]) -> CautiousAnswer:
    return CautiousAnswer(
        reason=reason,
        text=(
            "I could not validate an answer against the returned evidence."
            if reason == "invalid_answer"
            else "The model call failed; no answer was generated."
        ),
    )


def validate_selection(selection: FactSelection, allowed_ids: set[str]) -> bool:
    """Reject forged schema/IDs; a selection never supplies evidence or sentence text."""
    try:
        selection = FactSelection.model_validate(selection.model_dump(warnings=False))
    except ValidationError:
        return False
    return set(selection.fact_ids) <= allowed_ids
