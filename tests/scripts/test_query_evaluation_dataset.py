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
    assert dataset.version == "queries-1"
    assert dataset.baseline_version == "demo-1"
    supported = [case for case in dataset.cases if isinstance(case, SupportedCase)]
    declined = [case for case in dataset.cases if isinstance(case, DeclinedCase)]
    assert len(supported) == 12
    assert len(declined) == 6
    assert {case.scenario_key for case in supported} == {s.key for s in baseline.scenarios}
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
