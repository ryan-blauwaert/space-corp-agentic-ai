from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.answers.contracts import (
    ANSWER_OUTCOME,
    AnswerRequest,
    AnswerResponse,
    FactSelection,
    RecordReference,
    RenderedAnswer,
)
from app.queries.contracts import QueryContext, QueryResponse
from app.queries.service import QueryOutcome
from scripts.dataset_manifest import load_manifest
from scripts.query_evaluation_dataset import load_evaluation, resolve_case


def request_data(key="stock-at-reorder-point"):
    workspace = uuid4()
    case = next(c for c in load_evaluation().cases if c.key == key)
    resolved = resolve_case(case, load_manifest(), workspace)
    context = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace)
    query = QueryOutcome(
        context=context,
        planning_operation_id=uuid4(),
        resolution_operation_id=uuid4(),
        plan=resolved.expected_plan,
        response=QueryResponse(
            context=context, catalog_release_id=uuid4(), result=resolved.expected_result
        )
        if resolved.expected_result
        else None,
    )
    return {"question": resolved.question, "query": query.model_dump(mode="json")}


@pytest.mark.parametrize("key", [c.key for c in load_evaluation().cases])
def test_all_baseline_query_outcomes_can_supply_answer_input(key):
    request = AnswerRequest.model_validate(request_data(key))
    assert AnswerRequest.model_validate_json(request.model_dump_json()) == request
    assert request.question not in repr(request)


@pytest.mark.parametrize("field", ["request_id", "operation_id", "workspace_id"])
def test_evidence_context_cannot_be_swapped(field):
    data = request_data()
    data["query"]["response"]["context"][field] = str(uuid4())
    with pytest.raises(ValidationError, match="contexts must match"):
        AnswerRequest.model_validate(data)


def test_mismatched_domain_is_rejected():
    data = request_data()
    data["query"]["response"]["result"] = request_data("completed-work")["query"]["response"][
        "result"
    ]
    with pytest.raises(ValidationError, match="operations must match"):
        AnswerRequest.model_validate(data)


def test_pending_confirmation_cannot_carry_evidence():
    data = request_data()
    data["query"]["scope_status"] = "awaiting_confirmation"
    with pytest.raises(ValidationError, match="Pending scope"):
        AnswerRequest.model_validate(data)
    data["query"]["response"] = None
    assert AnswerRequest.model_validate(data).query.scope_status == "awaiting_confirmation"


def test_missing_evidence_can_be_represented_without_inventing_empty_results():
    data = request_data()
    data["query"]["response"] = None
    assert AnswerRequest.model_validate(data).query.response is None


@pytest.mark.parametrize("mutation", ["evidence", "approval"])
def test_declined_query_cannot_claim_evidence_or_approval(mutation):
    data = request_data("missing-facility")
    if mutation == "evidence":
        data["query"]["response"] = request_data()["query"]["response"]
    else:
        data["query"]["scope_status"] = "confirmed"
    with pytest.raises(ValidationError, match="Declined queries"):
        AnswerRequest.model_validate(data)


@pytest.mark.parametrize("text", ["", "  ", "x" * 12001])
def test_invalid_answer_text(text):
    with pytest.raises(ValidationError):
        RenderedAnswer(text=text, references=())


def test_selection_forbids_prose_values_and_authority():
    key = "a" * 64 + ":0"
    with pytest.raises(ValidationError, match="unique"):
        FactSelection(fact_ids=(key, key))
    for extra in (
        {"text": "quantity is 999"},
        {"value": 999},
        {"references": []},
        {"claims": []},
        {"workspace_id": str(uuid4())},
        {"coverage": "complete"},
    ):
        with pytest.raises(ValidationError):
            FactSelection.model_validate({"fact_ids": [key], **extra})
    with pytest.raises(ValidationError):
        RecordReference(entity="customer", record_id=uuid4())
    with pytest.raises(ValidationError):
        FactSelection(fact_ids=("invented",))


@pytest.mark.parametrize(
    "reason",
    [
        "no_results",
        "insufficient_evidence",
        "awaiting_confirmation",
        "declined",
        "invalid_answer",
        "model_failure",
    ],
)
def test_cautious_outcomes_have_no_record_claims(reason):
    outcome = ANSWER_OUTCOME.validate_python(
        {"status": "cautious", "reason": reason, "text": "Cannot answer from this evidence."}
    )
    context = AnswerRequest.model_validate(request_data()).query.context
    response = AnswerResponse(context=context, synthesis_operation_id=uuid4(), outcome=outcome)
    assert AnswerResponse.model_validate_json(response.model_dump_json()) == response
    with pytest.raises(ValidationError):
        ANSWER_OUTCOME.validate_python({**outcome.model_dump(), "references": []})


@pytest.mark.parametrize("coverage", ["complete", "partial"])
def test_answered_outcome_keeps_caller_owned_coverage(coverage):
    outcome = ANSWER_OUTCOME.validate_python(
        {
            "status": "answered",
            "coverage": coverage,
            "answer": {"text": "One matching record.", "references": []},
        }
    )
    assert outcome.coverage == coverage
    # RenderedAnswer is an output value; the renderer never accepts it as input.
