import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.queries.contracts import QUERY_PLAN, QUERY_RESULT
from scripts.dataset_manifest import DEFAULT_MANIFEST, load_manifest, operational_id, shared_id
from scripts.query_evaluation_dataset import (
    DEFAULT_EVALUATION,
    DeclinedCase,
    SupportedCase,
    load_evaluation,
    resolve_case,
)


def test_dataset_covers_baseline_and_declined_questions_without_mutating_baseline():
    before = DEFAULT_MANIFEST.read_bytes()
    baseline = load_manifest()
    dataset = load_evaluation()
    assert dataset.version == "queries-2"
    assert dataset.baseline_version == "demo-1"
    supported = [case for case in dataset.cases if isinstance(case, SupportedCase)]
    declined = [case for case in dataset.cases if isinstance(case, DeclinedCase)]
    assert len(supported) == 18
    assert len(declined) == 6
    assert {case.scenario_key for case in supported if case.scenario_key is not None} == {
        s.key for s in baseline.scenarios
    }
    assert set(dataset.prohibited_behaviors) == {
        "writes",
        "cross_workspace_reads",
        "raw_sql_execution",
        "unvalidated_execution",
    }
    for case in dataset.cases:
        resolved = resolve_case(case, baseline, uuid4())
        assert "@" not in resolved.question
        if isinstance(case, SupportedCase):
            assert resolved.execution_allowed
            assert QUERY_PLAN.validate_json(resolved.expected_plan.model_dump_json())
            assert QUERY_RESULT.validate_json(resolved.expected_result.model_dump_json())
        else:
            assert not resolved.execution_allowed
            assert resolved.expected_result is None
            assert resolved.expected_plan == case.expected
    assert DEFAULT_MANIFEST.read_bytes() == before


def test_expected_records_and_questions_resolve_for_each_workspace():
    baseline = load_manifest()
    case = next(case for case in load_evaluation().cases if case.key == "q2-stock-zero-and-unknown")
    first, second = UUID(int=1), UUID(int=2)
    a, b = [resolve_case(case, baseline, workspace) for workspace in (first, second)]
    assert a.expected_plan.equipment_unit_id == operational_id(first, "demo-1", "units", "U001")
    assert b.expected_plan.equipment_unit_id == operational_id(second, "demo-1", "units", "U001")
    assert str(a.expected_plan.equipment_unit_id) in a.question
    assert str(b.expected_plan.equipment_unit_id) in b.question
    assert a.expected_result.incident_ids != b.expected_result.incident_ids
    assert (
        a.expected_result.page.rows[0].inventory_id != b.expected_result.page.rows[0].inventory_id
    )
    for resolved in (a, b):
        rows = resolved.expected_result.page.rows
        assert len(rows) == 3
        assert rows[0].model_id == shared_id("demo-catalog-1", "models", "M01")
        assert rows[0].component_id == shared_id("demo-catalog-1", "components", "C01")
        assert [row.quantity_on_hand for row in rows] == [3, 0, None]
        assert rows[2].inventory_id is None
        assert len(resolved.expected_result.incident_ids) == 4


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "catalog",
        "digest",
        "missing-scenario",
        "unknown-scenario",
        "duplicate-key",
        "missing-prohibition",
        "unknown-prohibition",
        "unknown-question-reference",
        "missing-decline",
        "extra-field",
        "invalid-decline",
    ],
)
def test_bad_fixtures_fail_before_model_or_database_work(tmp_path, change):
    data = json.loads(DEFAULT_EVALUATION.read_text())
    if change == "version":
        data["baseline_version"] = "different"
    elif change == "catalog":
        data["catalog_version"] = "different"
    elif change == "digest":
        data["baseline_sha256"] = "0" * 64
    elif change == "missing-scenario":
        data["cases"].pop(0)
    elif change == "unknown-scenario":
        data["cases"][0]["scenario_key"] = "unknown"
    elif change == "duplicate-key":
        data["cases"].append(data["cases"][0])
    elif change == "missing-prohibition":
        data["prohibited_behaviors"].pop()
    elif change == "unknown-prohibition":
        data["prohibited_behaviors"].append("unknown")
    elif change == "unknown-question-reference":
        data["cases"][0]["question"] = "What about @units:UNKNOWN?"
    elif change == "missing-decline":
        data["cases"] = [case for case in data["cases"] if case["key"] != "missing-facility"]
    elif change == "extra-field":
        data["cases"][0]["workspace_id"] = str(uuid4())
    elif change == "invalid-decline":
        data["cases"][-1]["expected"]["reason"] = "whatever"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises((ValueError, ValidationError)):
        load_evaluation(path)


def test_baseline_content_change_rejected_even_with_same_version():
    data = load_manifest().model_dump(mode="json")
    data["scenarios"][0]["expected"]["rows"] = []
    changed = type(load_manifest()).model_validate(data)
    with pytest.raises(ValueError, match="digest mismatch"):
        load_evaluation(manifest=changed)


def test_canonical_examples_use_explicit_filters_not_implicit_question_rules():
    cases = {
        case.key: resolve_case(case, load_manifest(), UUID(int=1))
        for case in load_evaluation().cases
    }
    q1 = cases["q1-positive-unrelated-and-deduplicated"].expected_plan
    assert set(q1.unit_statuses) == {"degraded", "offline"}
    assert set(q1.incident_statuses) == {"open", "investigating"}
    q2 = cases["q2-stock-zero-and-unknown"].expected_plan
    assert set(q2.incident_statuses) == {"open", "investigating"}
    q3 = cases["q3-active-boundaries-and-distinct-targets"].expected_plan
    assert set(q3.statuses) == {"open", "in_progress", "blocked"}
    assert set(q3.priorities) == {"high", "critical"}
    q4 = cases["q4-same-fault-time-boundaries-and-distinct-incidents"]
    assert q4.expected_plan.fault_code == "AIRFLOW"
    assert q4.expected_result.count >= 2
    assert cases["q5-shortfall-and-equality"].expected_plan.below_reorder_point is True


def test_authored_variations_have_distinct_evidence_and_no_canonical_gate():
    baseline = load_manifest()
    cases = {c.key: resolve_case(c, baseline, UUID(int=1)) for c in load_evaluation().cases}
    assert cases["lunar-stock-threshold"].expected_plan.quantity.value == 2
    assert cases["lunar-stock-threshold"].expected_result.page.rows[0].quantity_on_hand == 0
    assert cases["stock-at-reorder-point"].expected_result.page.rows[0].shortfall == 0
    assert cases["completed-work"].expected_result.page.rows[0].status == "completed"
    assert cases["resolved-unit-incidents"].expected_plan.occurred is None
    assert cases["resolved-unit-incidents"].expected_result.page.rows[0].status == "resolved"
    assert cases["offline-equipment-without-incident"].expected_plan.incident_statuses is None
    assert cases["compatibility-without-incident"].expected_plan.incident_statuses is None
    assert cases["compatibility-without-incident"].expected_result.status == "matched"
    assert cases["compatibility-without-incident"].expected_result.incident_ids == ()


@pytest.mark.parametrize(
    "change",
    [
        "both-evidence",
        "neither-evidence",
        "invalid-plan",
        "unknown-plan-reference",
        "unknown-evidence-reference",
        "wrong-result",
        "invalid-result",
    ],
)
def test_authored_plan_and_result_templates_are_validated(tmp_path, change):
    data = json.loads(DEFAULT_EVALUATION.read_text())
    case = next(c for c in data["cases"] if c["key"] == "lunar-stock-threshold")
    if change == "both-evidence":
        case["scenario_key"] = "q5-empty"
    elif change == "neither-evidence":
        del case["expected_result"]
    elif change == "invalid-plan":
        case["expected_plan"]["sql"] = "SELECT 1"
    elif change == "unknown-plan-reference":
        case["expected_plan"]["component_id"] = "@components:UNKNOWN"
    elif change == "unknown-evidence-reference":
        case["expected_result"]["page"]["rows"][0]["inventory_id"] = "@inventory:UNKNOWN"
    elif change == "wrong-result":
        case["expected_result"] = {"operation": "work_orders", "page": {"rows": [], "total": 0}}
    else:
        case["expected_result"]["page"]["rows"][0]["shortfall"] = -1
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_evaluation(path)
