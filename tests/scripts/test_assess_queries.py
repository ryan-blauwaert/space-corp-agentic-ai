import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.assess_queries import DEFAULT_PROTOCOL, ROOT, assess
from scripts.evaluate_queries import CaseScore, EvaluationReport
from scripts.query_evaluation_dataset import load_evaluation


@pytest.fixture
def reports(tmp_path, monkeypatch):
    protocol = json.loads(DEFAULT_PROTOCOL.read_text())
    # Synthetic historical reports test aggregation, independently of current source changes.
    monkeypatch.setattr("scripts.assess_queries.prompt_digest", lambda: protocol["prompt_sha256"])
    monkeypatch.setattr(
        "scripts.assess_queries.implementation_digest", lambda: protocol["implementation_sha256"]
    )
    paths = []
    for version, spec in protocol["datasets"].items():
        dataset = load_evaluation(ROOT / spec["path"])
        for repeat in range(protocol["repetitions"]):
            cases = tuple(
                CaseScore(
                    key=c.key,
                    request_id=uuid4(),
                    operation_id=uuid4(),
                    returned_model_id="test-fixed-revision",
                    intent_match=True,
                    evidence_match=True,
                    execution_policy_match=True,
                    passed=True,
                    duration_ms=1,
                )
                for c in dataset.cases
            )
            report = EvaluationReport(
                run_id=uuid4(),
                started_at=datetime.now(UTC),
                dataset_version=version,
                dataset_purpose=dataset.purpose,
                dataset_sha256=spec["sha256"],
                baseline_version=dataset.baseline_version,
                baseline_sha256=dataset.baseline_sha256,
                catalog_version=dataset.catalog_version,
                model_id=protocol["model_id"],
                prompt_version=protocol["prompt_version"],
                prompt_sha256=protocol["prompt_sha256"],
                implementation_sha256=protocol["implementation_sha256"],
                max_attempts=1,
                cases=cases,
                total=len(cases),
                passed=len(cases),
                failed=0,
            )
            path = tmp_path / f"{version}-{repeat}.json"
            path.write_text(report.model_dump_json())
            paths.append(path)
    return paths


def change(path, mutate):
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))


def fail_case(data, index, category):
    data["cases"][index].update(passed=False, intent_match=False, failure_category=category)
    data["passed"] -= 1
    data["failed"] += 1


def test_complete_batch_reports_each_dataset_and_all_case_repetitions(reports):
    result = assess(reports)
    assert result["meets_quality_target"]
    assert len(result["run_ids"]) == 6
    for group in result["datasets"].values():
        assert group["observations"] == 72
        assert set(group["per_case_passes"].values()) == {3}


@pytest.mark.parametrize(
    "category", ["wrong_query", "wrong_evidence", "unexpected_execution", "execution_error"]
)
def test_critical_failure_cannot_be_hidden_by_high_aggregate_accuracy(reports, category):
    change(reports[-1], lambda d: fail_case(d, 0, category))
    result = assess(reports)
    assert not result["meets_quality_target"]
    assert not result["datasets"]["queries-holdout-1"]["meets_quality_target"]


def test_unnecessary_declines_are_counted_against_fixed_target(reports):
    change(reports[0], lambda d: fail_case(d, 0, "unnecessary_decline"))
    assert assess(reports)["meets_quality_target"]
    change(reports[1], lambda d: fail_case(d, 0, "unnecessary_decline"))
    change(reports[2], lambda d: fail_case(d, 0, "unnecessary_decline"))
    assert not assess(reports)["meets_quality_target"]


def test_decline_classification_has_separate_denominator(reports):
    change(reports[0], lambda d: fail_case(d, 23, "decline_category"))
    assert assess(reports)["meets_quality_target"]
    change(reports[1], lambda d: fail_case(d, 23, "decline_category"))
    assert not assess(reports)["meets_quality_target"]


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "prompt",
        "implementation",
        "model",
        "partial",
        "totals",
        "returned_model",
        "dataset",
        "old_report",
    ],
)
def test_incomplete_mixed_or_incompatible_batches_are_rejected(reports, fault):
    if fault == "missing":
        reports.pop()
    elif fault == "duplicate":
        reports[-1] = reports[0]
    else:

        def mutate(d):
            if fault == "prompt":
                d["prompt_sha256"] = "changed"
            elif fault == "implementation":
                d["implementation_sha256"] = "changed"
            elif fault == "model":
                d["model_id"] = "another-model"
            elif fault == "partial":
                d["cases"].pop()
            elif fault == "totals":
                d["passed"] = 0
            elif fault == "returned_model":
                d["cases"][0]["returned_model_id"] = "different-revision"
            elif fault == "dataset":
                d["dataset_sha256"] = "changed"
            else:
                d["report_version"] = "2"

        change(reports[0], mutate)
    with pytest.raises(ValueError):
        assess(reports)


def test_protocol_freeze_detects_current_implementation_drift(reports, monkeypatch):
    monkeypatch.setattr("scripts.assess_queries.implementation_digest", lambda: "changed")
    with pytest.raises(ValueError, match="Frozen implementation"):
        assess(reports)


def test_candidate_holdout_is_new_wording_not_relaxed_expectations():
    development = load_evaluation()
    holdout = load_evaluation(Path("data/evaluations/queries-holdout-1.json"))
    assert holdout.purpose == "holdout_candidate"
    assert development.purpose == "development"
    assert not {c.question for c in development.cases} & {c.question for c in holdout.cases}
    for original, new in zip(development.cases, holdout.cases, strict=True):
        assert original.model_dump(exclude={"key", "question"}) == new.model_dump(
            exclude={"key", "question"}
        )
