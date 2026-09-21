from uuid import uuid4

import pytest

from app.answers.contracts import AnswerRequest, FactSelection
from app.answers.validation import (
    cautious_response,
    evidence_references,
    failed_answer,
    validate_selection,
)
from app.queries.contracts import QueryContext, QueryResponse
from app.queries.service import QueryOutcome, needs_scope_confirmation
from scripts.dataset_manifest import load_manifest
from scripts.query_evaluation_dataset import load_evaluation, resolve_case


def request_for(key="stock-at-reorder-point", workspace=None):
    workspace = workspace or uuid4()
    case = next(c for c in load_evaluation().cases if c.key == key)
    resolved = resolve_case(case, load_manifest(), workspace)
    context = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace)
    return AnswerRequest(
        question=resolved.question,
        query=QueryOutcome(
            context=context,
            planning_operation_id=uuid4(),
            resolution_operation_id=uuid4(),
            plan=resolved.expected_plan,
            scope_status="confirmed"
            if resolved.expected_result and needs_scope_confirmation(resolved.expected_plan)
            else "not_required",
            response=QueryResponse(
                context=context, catalog_release_id=uuid4(), result=resolved.expected_result
            )
            if resolved.expected_result
            else None,
        ),
    )


def change_request(request, mutate):
    data = request.model_dump(mode="json")
    mutate(data["query"])
    return AnswerRequest.model_validate(data)


@pytest.mark.parametrize(
    "key,counts",
    [
        (
            "q1-positive-unrelated-and-deduplicated",
            {"facility": 1, "equipment_unit": 1, "incident": 4},
        ),
        (
            "q2-stock-zero-and-unknown",
            {"equipment_model": 1, "component": 3, "inventory": 2, "incident": 4},
        ),
        (
            "q3-active-boundaries-and-distinct-targets",
            {"work_order": 4, "facility": 1, "incident": 1, "equipment_unit": 2},
        ),
        ("resolved-unit-incidents", {"incident": 1, "equipment_unit": 1, "facility": 1}),
        ("stock-at-reorder-point", {"inventory": 1, "facility": 1, "component": 1}),
    ],
)
def test_reference_collection_includes_nested_and_relationship_evidence(key, counts):
    refs = evidence_references(request_for(key).query.response.result)
    assert {entity: sum(r.entity == entity for r in refs) for entity in counts} == counts
    assert len(refs) == sum(counts.values())


def test_missing_evidence_does_not_become_no_results():
    request = change_request(request_for("completed-work"), lambda q: q.update(response=None))
    assert cautious_response(request).reason == "insufficient_evidence"


@pytest.mark.parametrize(
    "key,phrase",
    [
        ("q2-no-incident", "No incident matched"),
        ("q2-no-compatibility", "No compatible components"),
    ],
)
def test_compatible_empty_statuses_remain_distinct(key, phrase):
    response = cautious_response(request_for(key))
    assert response.reason == "no_results"
    assert phrase in response.text


def test_failure_messages_are_not_empty_result_claims():
    for reason in ["invalid_answer", "model_failure"]:
        response = failed_answer(reason)
        assert response.reason == reason
        assert "No records matched" not in response.text


@pytest.mark.parametrize("state", ["awaiting_confirmation", "not_required"])
def test_broad_scope_without_approval_is_cautious(state):
    request = change_request(
        request_for("q1-positive-unrelated-and-deduplicated"),
        lambda q: q.update(scope_status=state, response=None),
    )
    assert cautious_response(request).reason == "awaiting_confirmation"


def test_selection_checks_exact_ids_and_revalidates_copies():
    key = "a" * 64 + ":0"
    assert validate_selection(FactSelection(fact_ids=(key,)), {key})
    assert not validate_selection(FactSelection(fact_ids=(key,)), set())
    assert not validate_selection(
        FactSelection(fact_ids=()).model_copy(update={"fact_ids": (key, key)}), {key}
    )
