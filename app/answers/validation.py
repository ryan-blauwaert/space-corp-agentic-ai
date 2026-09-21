"""Deterministic evidence checks, not a semantic judge for natural-language prose."""

import re
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from app.answers.contracts import (
    AnswerDraft,
    Answered,
    AnswerOutcome,
    AnswerRequest,
    CautiousAnswer,
    EvidenceClaim,
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
_UUID = re.compile(
    r"(?<![0-9a-f])(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})(?![0-9a-f])",
    re.IGNORECASE,
)


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


def claim_matches(claim: EvidenceClaim, result: QueryResult) -> bool:
    """Reject missing paths, null/zero confusion, coercion, and row/value swaps."""
    value: object = result.model_dump(mode="json")
    for part in claim.path:
        if isinstance(value, dict) and isinstance(part, str) and part in value:
            value = value[part]
        elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
            value = value[part]
        else:
            return False
    return type(value) is type(claim.value) and value == claim.value


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
                text = "No compatible components were returned for this query. This does not establish whether components are in stock."
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


def validate_draft(request: AnswerRequest, draft: AnswerDraft) -> AnswerOutcome:
    """Check declared facts and IDs; passing does not certify the prose's meaning.

    Invalid trusted input raises ValidationError. Invalid model output is withheld.
    This function never queries, generates, approves scope, or logs content.
    """
    request = AnswerRequest.model_validate(request.model_dump(warnings=False))
    cautious = cautious_response(request)
    if cautious is not None:
        return cautious
    try:
        draft = AnswerDraft.model_validate(draft.model_dump(warnings=False))
    except ValidationError:
        return failed_answer("invalid_answer")
    assert request.query.response is not None
    result = request.query.response.result
    allowed = evidence_references(result)
    supplied = set(draft.references)
    mentioned = {UUID(match[0]) for match in _UUID.finditer(draft.text)}
    if (
        not supplied <= allowed
        or not mentioned <= {reference.record_id for reference in supplied}
        or not draft.claims
        or not all(claim_matches(claim, result) for claim in draft.claims)
    ):
        return failed_answer("invalid_answer")
    page = result.page
    complete = page.offset == 0 and len(page.rows) == page.total
    if not complete:
        notice = f"Partial results: this page contains {len(page.rows)} of {page.total} matching records. "
        if len(notice) + len(draft.text) > 12000:
            return failed_answer("invalid_answer")
        draft = AnswerDraft(
            text=notice + draft.text, references=draft.references, claims=draft.claims
        )
    return Answered(answer=draft, coverage="complete" if complete else "partial")
