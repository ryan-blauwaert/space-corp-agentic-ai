import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.answers.service import RENDERER_VERSION
from scripts.answer_evaluation_dataset import load_answer_evaluation
from scripts.assess_answers import assess_answer_report, assess_batch
from scripts.dataset_manifest import digest, load_manifest
from scripts.evaluate_answers import evaluate_answers, write_report
from scripts.query_evaluation_dataset import load_evaluation


@pytest.fixture
def reviewed(tmp_path):
    # Synthetic review data tests gate behavior; it is not a real assessment/reviewer.
    report = evaluate_answers(
        load_evaluation(), load_answer_evaluation(), load_manifest(), UUID(int=1)
    )
    write_report(tmp_path, report, load_answer_evaluation())
    path = tmp_path / "review.json"
    review = json.loads(path.read_text())
    review["reviewer"] = "synthetic-test-review"
    for case in review["cases"]:
        case.update(
            required_facts_covered=[True] * len(case["required_facts_covered"]),
            supported_claim_count=1,
            unsupported_claims=[],
            cautious_and_scope_correct=True,
        )
    path.write_text(json.dumps(review))
    return tmp_path


def test_recorded_factual_assessment_can_pass_a_single_report(reviewed):
    result = assess_answer_report(reviewed / "report.json", reviewed / "review.json")
    assert result["all_cases_passed"]
    assert result["mode"] == "fixed_evidence"


@pytest.mark.parametrize(
    "change",
    [
        "unreviewed",
        "missing_case",
        "duplicate",
        "wrong_hash",
        "missing_fact",
        "no_reviewer",
        "zero_claims",
    ],
)
def test_incomplete_or_incompatible_review_cannot_pass(reviewed, change):
    path = reviewed / "review.json"
    data = json.loads(path.read_text())
    if change == "unreviewed":
        data["cases"][0]["unsupported_claims"] = None
    if change == "missing_case":
        data["cases"].pop()
    if change == "duplicate":
        data["cases"].append(data["cases"][0])
    if change == "wrong_hash":
        data["report_sha256"] = "0" * 64
    if change == "missing_fact":
        data["cases"][0]["required_facts_covered"] = []
    if change == "no_reviewer":
        data["reviewer"] = " "
    if change == "zero_claims":
        data["cases"][0]["supported_claim_count"] = 0
    path.write_text(json.dumps(data))
    with pytest.raises((ValueError, ValidationError)):
        assess_answer_report(reviewed / "report.json", path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("unsupported_claims", ["A valid record was described with a false quantity."]),
        ("required_facts_covered", [False]),
        ("cautious_and_scope_correct", False),
    ],
)
def test_false_facts_omissions_and_scope_errors_are_failures(reviewed, field, value):
    path = reviewed / "review.json"
    data = json.loads(path.read_text())
    data["cases"][0][field] = value
    path.write_text(json.dumps(data))
    assert not assess_answer_report(reviewed / "report.json", path)["all_cases_passed"]


def test_report_changes_invalidate_completed_review(reviewed):
    path = reviewed / "report.json"
    data = json.loads(path.read_text())
    data["cases"][0]["checks"]["state"] = False
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        assess_answer_report(path, reviewed / "review.json")
    review = json.loads((reviewed / "review.json").read_text())
    review["report_sha256"] = digest(data)
    (reviewed / "review.json").write_text(json.dumps(review))
    with pytest.raises(ValueError, match="automatic"):
        assess_answer_report(path, reviewed / "review.json")


def test_batch_requires_predeclared_number_of_runs(reviewed, tmp_path):
    from scripts.evaluate_answers import answer_digest

    protocol = {
        "implementation_sha256": answer_digest(),
        "datasets": {"queries-3": {}},
        "repetitions": 3,
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="All planned"):
        assess_batch(path, [reviewed])


@pytest.fixture
def batch(tmp_path):
    from scripts.evaluate_answers import answer_digest, automatic_checks
    from scripts.evaluate_queries import prompt_digest
    from scripts.query_evaluation_dataset import resolve_case

    queries, answers, manifest = load_evaluation(), load_answer_evaluation(), load_manifest()
    folders = []
    for index in range(3):
        folder = tmp_path / f"run-{index}"
        folder.mkdir()
        folders.append(folder)
        report = evaluate_answers(queries, answers, manifest, UUID(int=1))
        cases = []
        for case, fixture in zip(report.cases, queries.cases, strict=True):
            turn = case.turn
            turn = turn.model_copy(
                update={
                    "request": turn.request.model_copy(
                        update={
                            "query": turn.request.query.model_copy(
                                update={"returned_model_id": "test-model"}
                            )
                        }
                    )
                }
            )
            ctx = turn.response.context
            base = {"request_id": str(ctx.request_id), "query_operation_id": str(ctx.operation_id)}
            events = [
                {**base, "event": name, "operation_id": str(turn.response.synthesis_operation_id)}
                for name in ("answer_render", "answer_operation")
            ]
            events += [
                {
                    **base,
                    "event": "query_planning",
                    "operation_id": str(turn.request.query.planning_operation_id),
                },
                {
                    **base,
                    "event": "query_resolution",
                    "operation_id": str(turn.request.query.resolution_operation_id),
                },
                {**base, "event": "model_attempt", "attempt_count": 1},
            ]
            if turn.request.query.response:
                events.append({**base, "event": "query_execution"})
            checks = automatic_checks(
                resolve_case(fixture, manifest, UUID(int=1)), turn, events, live=True
            )
            cases.append(
                case.model_copy(update={"turn": turn, "events": tuple(events), "checks": checks})
            )
        report = report.model_copy(
            update={
                "mode": "live_scope_confirmation",
                "model_id": "test-model",
                "reasoning_effort": "medium",
                "max_attempts": 1,
                "cases": tuple(cases),
            }
        )
        write_report(folder, report, answers)
        review = json.loads((folder / "review.json").read_text())
        review["reviewer"] = "synthetic-test-review"
        for case in review["cases"]:
            case.update(
                required_facts_covered=[True] * len(case["required_facts_covered"]),
                supported_claim_count=1,
                unsupported_claims=[],
                cautious_and_scope_correct=True,
            )
        (folder / "review.json").write_text(json.dumps(review))
    protocol = {
        "version": "test",
        "implementation_sha256": answer_digest(),
        "prompt_sha256": prompt_digest(),
        "renderer_version": RENDERER_VERSION,
        "model_id": "test-model",
        "reasoning_effort": "medium",
        "repetitions": 3,
        "minimum_answerable_pass_rate": 0.95,
        "datasets": {
            queries.version: {
                "query_sha256": digest(queries.model_dump(mode="json")),
                "answer_version": answers.version,
                "answer_sha256": digest(answers.model_dump(mode="json")),
            }
        },
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    return path, folders


def test_complete_batch_meets_thresholds(batch):
    protocol, folders = batch
    assert assess_batch(protocol, folders)["meets_quality_target"]


@pytest.mark.parametrize(
    "change", ["duplicate", "mode", "model", "missing_review", "unsupported", "all_repetitions"]
)
def test_batch_cannot_hide_critical_failures_or_mix_runs(batch, change):
    protocol, folders = batch
    if change == "duplicate":
        folders[1] = folders[0]
    if change in ("mode", "model"):
        p = folders[0] / "report.json"
        data = json.loads(p.read_text())
        data["mode" if change == "mode" else "model_id"] = (
            "fixed_evidence" if change == "mode" else "other-model"
        )
        p.write_text(json.dumps(data))
    if change == "missing_review":
        (folders[0] / "review.json").unlink()
    if change in ("unsupported", "all_repetitions"):
        for folder in folders if change == "all_repetitions" else folders[:1]:
            p = folder / "review.json"
            data = json.loads(p.read_text())
            if change == "unsupported":
                data["cases"][0]["unsupported_claims"] = ["Unsupported cause"]
            else:
                data["cases"][0]["required_facts_covered"] = [False]
            p.write_text(json.dumps(data))
        assert not assess_batch(protocol, folders)["meets_quality_target"]
    else:
        with pytest.raises((ValueError, FileNotFoundError)):
            assess_batch(protocol, folders)


@pytest.mark.parametrize("method", ["evidence_inspection", "automated_fact_checks"])
def test_factual_assessment_accepts_method_without_reviewer_type_restriction(reviewed, method):
    path = reviewed / "review.json"
    data = json.loads(path.read_text())
    data["review_kind"] = method
    data["reviewer"] = "test-assessment-process"
    path.write_text(json.dumps(data))
    assert assess_answer_report(reviewed / "report.json", path)["all_cases_passed"]


def replace_with_safe_decline(folder, key, reason="unsupported_question"):
    from app.answers.rendering import render_answer
    from app.queries.contracts import DeclinedPlan
    from scripts.evaluate_answers import AnswerEvaluationReport, automatic_checks
    from scripts.query_evaluation_dataset import resolve_case

    report = AnswerEvaluationReport.model_validate_json((folder / "report.json").read_text())
    rows = []
    for case in report.cases:
        if case.key == key:
            query = case.turn.request.query.model_copy(
                update={
                    "plan": DeclinedPlan(operation="declined", reason=reason),
                    "response": None,
                    "scope_status": "not_required",
                }
            )
            request = case.turn.request.model_copy(update={"query": query})
            turn = case.turn.model_copy(
                update={
                    "request": request,
                    "response": case.turn.response.model_copy(
                        update={"outcome": render_answer(request)}
                    ),
                }
            )
            events = tuple(e for e in case.events if e["event"] != "query_execution")
            expected = resolve_case(
                next(c for c in load_evaluation().cases if c.key == key),
                load_manifest(),
                report.workspace_id,
            )
            case = case.model_copy(
                update={
                    "turn": turn,
                    "events": events,
                    "checks": automatic_checks(expected, turn, events, live=True),
                }
            )
        rows.append(case)
    report = report.model_copy(update={"cases": tuple(rows)})
    (folder / "report.json").write_text(report.model_dump_json())
    path = folder / "review.json"
    review = json.loads(path.read_text())
    review["report_sha256"] = digest(report.model_dump(mode="json"))
    for row in review["cases"]:
        if row["key"] == key:
            row["required_facts_covered"] = [False] * len(row["required_facts_covered"])
            row["cautious_and_scope_correct"] = False
    path.write_text(json.dumps(review))


def test_one_unnecessary_empty_query_refusal_is_within_supported_allowance(batch):
    protocol, folders = batch
    replace_with_safe_decline(folders[0], "q3-empty")
    result = assess_batch(protocol, folders)["datasets"]["queries-3"]
    assert result["supported_cases"] == 54
    assert result["declined_cases"] == 18
    assert result["answerable_pass_rate"] == 53 / 54
    assert result["meets_quality_target"]


def test_repeated_empty_query_refusal_still_fails(batch):
    protocol, folders = batch
    for folder in folders:
        replace_with_safe_decline(folder, "q3-empty")
    assert not assess_batch(protocol, folders)["meets_quality_target"]


def test_decline_category_allowance(batch):
    protocol, folders = batch
    replace_with_safe_decline(folders[0], "missing-facility")
    assert assess_batch(protocol, folders)["meets_quality_target"]
    replace_with_safe_decline(folders[1], "missing-facility")
    assert not assess_batch(protocol, folders)["meets_quality_target"]


def test_historical_assessment_is_explicit_and_preserves_source_binding(batch, monkeypatch):
    protocol, folders = batch
    monkeypatch.setattr("scripts.assess_answers.answer_digest", lambda: "changed")
    with pytest.raises(ValueError, match="Frozen implementation"):
        assess_batch(protocol, folders)
    result = assess_batch(protocol, folders, historical=True)
    assert result["historical"] and not result["current_implementation"]
    path = folders[0] / "report.json"
    report = json.loads(path.read_text())
    report["implementation_sha256"] = "wrong"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Incompatible"):
        assess_batch(protocol, folders, historical=True)
