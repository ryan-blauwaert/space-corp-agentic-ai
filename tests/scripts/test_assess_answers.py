import json
from uuid import UUID

import pytest
from pydantic import ValidationError

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


def test_completed_review_can_pass_a_single_report(reviewed):
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
        "renderer_version": "1",
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
