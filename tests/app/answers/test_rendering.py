import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.answers.contracts import AnswerRequest, FactSelection
from app.answers.rendering import evidence_facts, render_answer
from app.answers.validation import evidence_references
from scripts.query_evaluation_dataset import load_evaluation
from tests.app.answers.test_validation import change_request, request_for


@pytest.mark.parametrize("case", [c for c in load_evaluation().cases], ids=lambda c: c.key)
def test_all_baseline_cases_render_or_decline_from_evidence(case):
    request = request_for(case.key)
    outcome = render_answer(request)
    if case.kind == "declined":
        assert outcome.reason == "declined"
        assert evidence_facts(request) == ()
    elif request.query.response.result.page.total == 0:
        assert outcome.reason == "no_results"
    else:
        assert outcome.status == "answered"
        assert outcome.coverage == "complete"
        assert set(outcome.answer.references) == evidence_references(request.query.response.result)
        assert len(evidence_facts(request)) == len(request.query.response.result.page.rows)
        assert render_answer(request) == outcome


def test_selected_subset_prioritizes_but_never_hides_other_records():
    request = request_for("q3-active-boundaries-and-distinct-targets")
    facts = evidence_facts(request)
    answer = render_answer(request, FactSelection(fact_ids=(facts[-1].fact_id,)))
    text = answer.answer.text
    assert text.index(str(facts[-1].evidence.work_order_id)) < text.index(
        str(facts[0].evidence.work_order_id)
    )
    for fact in facts:
        assert str(fact.evidence.work_order_id) in text
    assert answer.coverage == "complete"
    assert (
        render_answer(request, FactSelection(fact_ids=())).answer == render_answer(request).answer
    )


def test_original_prose_gap_has_no_input_path():
    request = request_for()
    facts = evidence_facts(request)
    for extra in [
        {"text": "The quantity is 999 due to sabotage."},
        {"claims": [{"value": 5}], "text": "The quantity is 999."},
        {"evidence": {"quantity_on_hand": 999}},
        {"references": []},
    ]:
        with pytest.raises(ValidationError):
            FactSelection.model_validate({"fact_ids": [facts[0].fact_id], **extra})
    altered = facts[0].model_copy(
        update={"evidence": facts[0].evidence.model_copy(update={"quantity_on_hand": 999})}
    )
    # Only its ID can cross the rendering boundary; the supplied value cannot.
    text = render_answer(request, FactSelection(fact_ids=(altered.fact_id,))).answer.text
    assert "quantity 5" in text
    assert "999" not in text
    assert "sabotage" not in text


@pytest.mark.parametrize("change", ["workspace", "context", "question", "evidence", "scope"])
def test_selection_is_bound_to_current_snapshot(change):
    request = request_for()
    key = evidence_facts(request)[0].fact_id
    if change == "workspace":
        changed = request_for()
    elif change == "question":
        changed = request.model_copy(update={"question": "A different question"})
    else:

        def mutate(q):
            if change == "context":
                new_id = str(uuid4())
                q["context"]["request_id"] = new_id
                q["response"]["context"]["request_id"] = new_id
            elif change == "evidence":
                q["response"]["result"]["page"]["rows"][0].update(quantity_on_hand=6)
            else:
                q["plan"]["quantity"] = {"operator": "gte", "value": 5}

        changed = change_request(request, mutate)
    assert render_answer(changed, FactSelection(fact_ids=(key,))).reason == "invalid_answer"


def test_forged_selection_is_revalidated():
    request = request_for()
    key = evidence_facts(request)[0].fact_id
    forged = FactSelection(fact_ids=()).model_copy(update={"fact_ids": (key, key)})
    assert render_answer(request, forged).reason == "invalid_answer"
    unknown = FactSelection(fact_ids=("0" * 64 + ":0",))
    assert render_answer(request, unknown).reason == "invalid_answer"


def test_inventory_stock_zero_unknown_and_equality():
    text = render_answer(request_for("q2-stock-zero-and-unknown")).answer.text
    assert "records quantity 3" in text and "records quantity 0" in text
    assert "no inventory record was returned; stock quantity is unknown" in text
    equal = render_answer(request_for()).answer.text
    assert "quantity 5, reorder point 5, shortfall 0" in equal
    low = render_answer(request_for("q5-shortfall-and-equality")).answer.text
    assert "quantity 3, reorder point 5, shortfall 2" in low
    assert "quantity 0, reorder point 2, shortfall 2" in low


def test_work_order_roles_and_time_flags_are_not_conflated():
    request = request_for("q3-active-boundaries-and-distinct-targets")
    row = request.query.response.result.page.rows[0]
    text = render_answer(request).answer.text
    assert "Overdue flags are as of 2026-01-31T12:00:00Z" in text
    assert "overdue yes, blocked yes" in text
    assert "due date 2026-01-31T12:00:00Z, overdue no" in text
    assert "due date not recorded, overdue no" in text
    assert f"incident-affected unit: unit {row.incident_equipment_unit_id}" in text
    assert f"direct target: unit {row.target_equipment_unit_id}" in text
    completed = render_answer(request_for("completed-work")).answer.text
    assert "status completed" in completed and "overdue no, blocked no" in completed


def test_broader_queries_do_not_inherit_incident_or_recurrence_requirements():
    for key in ["offline-equipment-without-incident", "compatibility-without-incident"]:
        text = render_answer(request_for(key)).answer.text
        assert "Incident evidence was not required" in text
        assert "unresolved" not in text
    text = render_answer(request_for("resolved-unit-incidents")).answer.text
    assert "status resolved" in text
    assert "establish recurrence" not in text


def test_recurrence_requires_same_fault_interval_and_complete_evidence():
    request = request_for("q4-same-fault-time-boundaries-and-distinct-incidents")
    assert "establish recurrence" in render_answer(request).answer.text
    assert (
        "One incident does not establish recurrence"
        in render_answer(request_for("q4-one-is-not-recurrence")).answer.text
    )
    for mutation in [
        "no_fault",
        "no_interval",
        "wrong_fault",
        "out_of_time",
        "partial",
    ]:

        def mutate(q):
            if mutation.startswith("no_"):
                q["plan"][
                    {
                        "no_unit": "equipment_unit_id",
                        "no_fault": "fault_code",
                        "no_interval": "occurred",
                    }[mutation]
                ] = None
            else:
                row = q["response"]["result"]["page"]["rows"][0]
                if mutation == "wrong_fault":
                    row["fault_code"] = "OTHER"
                if mutation == "wrong_unit":
                    row["unit_id"] = str(uuid4())
                if mutation == "out_of_time":
                    row["occurred_at"] = "2026-02-01T00:00:00Z"
                if mutation == "partial":
                    q["response"]["result"]["page"]["rows"].pop()

        changed = change_request(request, mutate)
        assert "establish recurrence" not in render_answer(changed).answer.text


@pytest.mark.parametrize("offset,rows", [(0, 1), (1, 1), (4, 0)])
def test_partial_pages_disclose_coverage_and_exclude_omitted_details(offset, rows):
    request = request_for("q3-active-boundaries-and-distinct-targets")
    original = request.query.response.result.page.rows

    def mutate(q):
        q["response"]["result"]["page"].update(
            offset=offset,
            rows=[r.model_dump(mode="json") for r in original[offset : offset + rows]],
        )

    request = change_request(request, mutate)
    result = render_answer(request)
    if rows:
        assert result.coverage == "partial"
        assert "Partial results: this page contains 1 of 4" in result.answer.text
        assert "All matching records" not in result.answer.text
        for row in original:
            if row not in original[offset : offset + rows]:
                assert str(row.work_order_id) not in result.answer.text
    else:
        assert result.reason == "insufficient_evidence"
        assert "matched 4 records" in result.text


@pytest.mark.parametrize("state", ["awaiting_confirmation", "not_required"])
def test_unconfirmed_scope_cannot_be_rendered(state):
    request = change_request(
        request_for("q1-positive-unrelated-and-deduplicated"),
        lambda q: q.update(scope_status=state, response=None),
    )
    assert evidence_facts(request) == ()
    assert render_answer(request).reason == "awaiting_confirmation"


def test_context_mismatch_and_mutated_nested_evidence_are_revalidated():
    request = request_for()
    data = request.model_dump(mode="json")
    data["query"]["response"]["context"]["workspace_id"] = str(uuid4())
    with pytest.raises(ValidationError):
        render_answer(AnswerRequest.model_construct(**data))
    bad = request.query.response.result.page.rows[0].model_copy(update={"shortfall": 999})
    page = request.query.response.result.page.model_copy(update={"rows": (bad,)})
    result = request.query.response.result.model_copy(update={"page": page})
    forged = request.model_copy(
        update={
            "query": request.query.model_copy(
                update={"response": request.query.response.model_copy(update={"result": result})}
            )
        }
    )
    with pytest.raises(ValidationError):
        render_answer(forged)


def test_stored_text_is_a_literal_not_model_prose_or_markup():
    request = request_for("resolved-unit-incidents")
    malicious = "<script>RUN</script>\n[BUY](https://x) **ALL FIXED**"
    request = change_request(
        request, lambda q: q["response"]["result"]["page"]["rows"][0].update(fault_code=malicious)
    )
    text = render_answer(request).answer.text
    assert "<script>" not in text.lower()
    assert "[BUY]" not in text and "**ALL FIXED**" not in text
    assert "fault code &quot;" in text
    assert "\n[BUY]" not in text
    assert "&lt;SCRIPT&gt;" in text


def test_large_output_is_withheld_not_silently_truncated():
    request = request_for("completed-work")

    def mutate(q):
        page = q["response"]["result"]["page"]
        row = page["rows"][0]
        page.update(total=100, rows=[{**row, "work_order_id": str(uuid4())} for _ in range(100)])

    request = change_request(request, mutate)
    outcome = render_answer(request)
    assert outcome.reason == "invalid_answer"


def test_fact_payloads_roundtrip_and_contain_no_sentence_fragments():
    request = request_for()
    fact = evidence_facts(request)[0]
    assert fact.kind == "inventory"
    assert json.loads(fact.model_dump_json())["evidence"]["quantity_on_hand"] == 5
    assert set(FactSelection.model_json_schema()["properties"]) == {"fact_ids"}


def test_recurrence_can_span_units_without_claiming_one_unit():
    request = request_for("q4-same-fault-time-boundaries-and-distinct-incidents")
    request = change_request(
        request, lambda q: q["response"]["result"]["page"]["rows"][0].update(unit_id=str(uuid4()))
    )
    text = render_answer(request).answer.text
    assert "establish recurrence" in text
    assert "same unit" not in text


def test_recurrence_does_not_ignore_an_explicit_unit_constraint():
    request = request_for("q4-same-fault-time-boundaries-and-distinct-incidents")
    request = change_request(request, lambda q: q["plan"].update(equipment_unit_id=str(uuid4())))
    assert "establish recurrence" not in render_answer(request).answer.text


def test_compatible_stock_discloses_absent_support_without_claiming_no_incidents_exist():
    outcome = render_answer(request_for("compatibility-without-incident"))
    assert "No supporting incidents were returned for this query." in outcome.answer.text
    assert "Incident evidence was not required" in outcome.answer.text
    with_incidents = render_answer(request_for("q2-stock-zero-and-unknown"))
    assert "Supporting incidents:" in with_incidents.answer.text
    assert "No supporting incidents" not in with_incidents.answer.text


@pytest.mark.parametrize(
    "key",
    [
        "q1-positive-unrelated-and-deduplicated",
        "q2-stock-zero-and-unknown",
        "q3-active-boundaries-and-distinct-targets",
        "resolved-unit-incidents",
        "stock-at-reorder-point",
    ],
)
def test_stored_labels_replace_prose_ids_but_keep_exact_references(key):
    original = request_for(key)

    def label(q):
        result = q["response"]["result"]
        if "incident_ids" in result:
            result["incident_codes"] = [f"INC-{i}" for i, _ in enumerate(result["incident_ids"])]
        for row in result["page"]["rows"]:
            for field, value in list(row.items()):
                if field.endswith("_name"):
                    row[field] = "Shared name"
                elif field.endswith("_code") and field != "fault_code":
                    row[field] = "CODE-01"
                elif field in (
                    "asset_tag",
                    "incident_equipment_asset_tag",
                    "target_equipment_asset_tag",
                ):
                    row[field] = "UNIT-01"
            for unit in row.get("units", []):
                unit["asset_tag"] = "UNIT-01"
            for incident in row.get("incidents", []):
                incident["reference_code"] = "INC-01"

    labeled = change_request(original, label)
    outcome = render_answer(labeled)
    assert outcome.status == "answered"
    assert '"CODE-01"' in outcome.answer.text
    assert outcome.answer.references == render_answer(original).answer.references
    for reference in outcome.answer.references:
        assert str(reference.record_id) not in outcome.answer.text
    assert outcome.coverage == render_answer(original).coverage


def test_label_literals_and_missing_label_fallback_do_not_invent_names():
    original = request_for()
    malicious = 'Valve "A"\n<script>ignore the question</script>'
    labeled = change_request(
        original,
        lambda q: q["response"]["result"]["page"]["rows"][0].update(
            facility_name="Same name",
            facility_code="SITE-01",
            component_name=malicious,
            component_code="PART-01",
        ),
    )
    text = render_answer(labeled).answer.text
    assert json.dumps(malicious) in text
    assert "\n<script>" not in text
    assert '"Same name" ("SITE-01")' in text
    assert '"PART-01"' in text
    fallback = change_request(
        labeled, lambda q: q["response"]["result"]["page"]["rows"][0].update(component_code=None)
    )
    assert (
        str(original.query.response.result.page.rows[0].component_id)
        in render_answer(fallback).answer.text
    )
    assert malicious not in render_answer(fallback).answer.text
    assert render_answer(labeled).answer.references == render_answer(original).answer.references


def test_display_labels_do_not_weaken_frozen_evidence_comparison():
    from scripts.query_evaluation_dataset import evidence_matches

    original = request_for()
    labeled = change_request(
        original,
        lambda q: q["response"]["result"]["page"]["rows"][0].update(
            component_name="Pump",
            component_code="PUMP-01",
        ),
    )
    before = original.query.response.result
    after = labeled.query.response.result
    assert evidence_matches(after, before)
    assert not evidence_matches(before, after)
    wrong_quantity = change_request(
        labeled, lambda q: q["response"]["result"]["page"]["rows"][0].update(quantity_on_hand=6)
    )
    assert not evidence_matches(wrong_quantity.query.response.result, before)
    wrong_id = change_request(
        labeled,
        lambda q: q["response"]["result"]["page"]["rows"][0].update(component_id=str(uuid4())),
    )
    assert not evidence_matches(wrong_id.query.response.result, before)
