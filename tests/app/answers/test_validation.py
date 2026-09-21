from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.answers.contracts import AnswerDraft, AnswerRequest, EvidenceClaim, RecordReference
from app.answers.validation import (
    cautious_response,
    claim_matches,
    evidence_references,
    failed_answer,
    validate_draft,
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


def draft_for(request):
    result = request.query.response.result
    return AnswerDraft(
        text=f"The query returned {result.page.total} matching records.",
        references=(),
        claims=(EvidenceClaim(path=("page", "total"), value=result.page.total),),
    )


def change_request(request, mutate):
    data = request.model_dump(mode="json")
    mutate(data["query"])
    return AnswerRequest.model_validate(data)


@pytest.mark.parametrize("case", [c for c in load_evaluation().cases], ids=lambda c: c.key)
def test_baseline_preflight_and_nonempty_success(case):
    request = request_for(case.key)
    response = cautious_response(request)
    if case.kind == "declined":
        assert response.reason == "declined"
    elif request.query.response.result.page.total == 0:
        assert response.reason == "no_results"
    else:
        assert response is None
        assert validate_draft(request, draft_for(request)).coverage == "complete"


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


@pytest.mark.parametrize(
    "identity_source", ["invented", "context", "other_workspace", "wrong_entity", "plan_only"]
)
def test_reference_membership_rejects_unsupported_identities(identity_source):
    request = request_for()
    result = request.query.response.result
    record = RecordReference(entity="inventory", record_id=result.page.rows[0].inventory_id)
    if identity_source == "invented":
        record = record.model_copy(update={"record_id": uuid4()})
    if identity_source == "context":
        record = record.model_copy(update={"record_id": request.query.context.workspace_id})
    if identity_source == "other_workspace":
        record = record.model_copy(
            update={"record_id": request_for().query.response.result.page.rows[0].inventory_id}
        )
    if identity_source == "wrong_entity":
        record = record.model_copy(update={"entity": "work_order"})
    if identity_source == "plan_only":
        request = request_for("compatibility-without-incident")
        record = RecordReference(
            entity="equipment_unit", record_id=request.query.plan.equipment_unit_id
        )
    draft = draft_for(request).model_copy(update={"references": (record,)})
    assert validate_draft(request, draft).reason == "invalid_answer"


@pytest.mark.parametrize(
    "format_id",
    [
        str,
        lambda x: x.hex,
        lambda x: str(x).upper(),
        lambda x: "{" + str(x) + "}",
        lambda x: "urn:uuid:" + str(x),
    ],
)
def test_identifiers_in_prose_need_valid_citations(format_id):
    request = request_for()
    record = RecordReference(
        entity="inventory", record_id=request.query.response.result.page.rows[0].inventory_id
    )
    draft = draft_for(request).model_copy(update={"text": format_id(record.record_id)})
    assert validate_draft(request, draft).reason == "invalid_answer"
    assert (
        validate_draft(request, draft.model_copy(update={"references": (record,)})).status
        == "answered"
    )
    invented = draft.model_copy(update={"text": format_id(uuid4()), "references": (record,)})
    assert validate_draft(request, invented).reason == "invalid_answer"


@pytest.mark.parametrize(
    "path,value,expected",
    [
        (("page", "rows", 0, "quantity_on_hand"), 5, True),
        (("page", "rows", 0, "quantity_on_hand"), 0, False),
        (("page", "rows", 0, "quantity_on_hand"), "5", False),
        (("page", "rows", 0, "quantity_on_hand"), True, False),
        (("page", "rows", 0, "quantity_on_hand"), None, False),
        (("page", "rows", 0, "cause"), "poor maintenance", False),
        (("page", "rows", 99, "quantity_on_hand"), 5, False),
        (("page", "rows", "0", "quantity_on_hand"), 5, False),
        (("__class__",), "inventory", False),
        (("page", "rows"), None, False),
    ],
)
def test_explicit_claims_compare_exact_values_at_exact_paths(path, value, expected):
    request = request_for()
    claim = EvidenceClaim(path=path, value=value)
    assert claim_matches(claim, request.query.response.result) is expected
    draft = draft_for(request).model_copy(update={"claims": (claim,)})
    assert (validate_draft(request, draft).status == "answered") is expected


def test_stock_null_zero_and_row_identity_are_not_interchangeable():
    result = request_for("q2-stock-zero-and-unknown").query.response.result
    for index, correct in enumerate([3, 0, None]):
        for value in [3, 0, None]:
            assert claim_matches(
                EvidenceClaim(path=("page", "rows", index, "quantity_on_hand"), value=value), result
            ) is (value == correct)


@pytest.mark.parametrize("path", [("page", "rows", -1), ("page", "rows", True), (), ("page", 1.5)])
def test_invalid_claim_paths(path):
    with pytest.raises(ValidationError):
        EvidenceClaim(path=path, value=1)


def test_claim_values_are_scalar_without_coercion():
    for value in [1.5, {"x": 1}, [1]]:
        with pytest.raises(ValidationError):
            EvidenceClaim(path=("page", "total"), value=value)


def test_real_references_do_not_excuse_false_explicit_facts():
    request = request_for("completed-work")
    record = RecordReference(
        entity="work_order", record_id=request.query.response.result.page.rows[0].work_order_id
    )
    for field, value in [("status", "open"), ("overdue", True), ("cause", "neglect")]:
        draft = AnswerDraft(
            text="A claim about a real order.",
            references=(record,),
            claims=(EvidenceClaim(path=("page", "rows", 0, field), value=value),),
        )
        assert validate_draft(request, draft).reason == "invalid_answer"


def test_missing_claims_and_forged_draft_are_withheld():
    request = request_for()
    assert (
        validate_draft(request, AnswerDraft(text="Stock is low.", references=())).reason
        == "invalid_answer"
    )
    assert (
        validate_draft(request, draft_for(request).model_copy(update={"text": ""})).reason
        == "invalid_answer"
    )


@pytest.mark.parametrize("state", ["awaiting_confirmation", "not_required"])
def test_broad_scope_without_approval_never_gets_an_answer(state):
    request = change_request(
        request_for("q1-positive-unrelated-and-deduplicated"),
        lambda q: q.update(scope_status=state, response=None),
    )
    assert cautious_response(request).reason == "awaiting_confirmation"
    assert (
        validate_draft(request, AnswerDraft(text="Invented answer", references=())).reason
        == "awaiting_confirmation"
    )


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


@pytest.mark.parametrize("offset,rows", [(0, 1), (1, 1), (4, 0)])
def test_partial_and_empty_pages_do_not_claim_no_matches(offset, rows):
    request = request_for("q3-active-boundaries-and-distinct-targets")

    def page(q):
        p = q["response"]["result"]["page"]
        p.update(offset=offset, rows=p["rows"][offset : offset + rows])

    request = change_request(request, page)
    outcome = validate_draft(request, draft_for(request))
    if rows:
        assert outcome.coverage == "partial"
        assert outcome.answer.text.startswith("Partial results:")
        # Records on omitted pages cannot be cited.
        omitted = request_for(
            "q3-active-boundaries-and-distinct-targets", request.query.context.workspace_id
        ).query.response.result.page.rows[3]
        draft = draft_for(request).model_copy(
            update={
                "references": (
                    RecordReference(entity="work_order", record_id=omitted.work_order_id),
                )
            }
        )
        assert validate_draft(request, draft).reason == "invalid_answer"
    else:
        assert outcome.reason == "insufficient_evidence"
        assert "matched 4 records" in outcome.text


def test_partial_notice_cannot_overflow_text_bound():
    request = change_request(
        request_for("completed-work"), lambda q: q["response"]["result"]["page"].update(total=2)
    )
    draft = draft_for(request).model_copy(update={"text": "x" * 12000})
    assert validate_draft(request, draft).reason == "invalid_answer"


def test_untrusted_context_copy_is_revalidated():
    request = request_for()
    wrong = request.query.response.model_copy(update={"context": request_for().query.context})
    forged = request.model_copy(
        update={"query": request.query.model_copy(update={"response": wrong})}
    )
    with pytest.raises(ValidationError):
        validate_draft(forged, draft_for(request))


def test_failure_messages_are_not_empty_result_claims():
    for reason in ["invalid_answer", "model_failure"]:
        response = failed_answer(reason)
        assert response.reason == reason
        assert "No records matched" not in response.text


def test_known_limit_real_claims_do_not_prove_prose_truth():
    request = request_for()
    draft = draft_for(request).model_copy(update={"text": "The quantity is 999 due to sabotage."})
    # Deliberate regression documentation: no keyword rules or claim/prose equivalence claim.
    assert validate_draft(request, draft).status == "answered"
