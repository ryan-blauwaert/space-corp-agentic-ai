import json
from uuid import UUID, uuid4

import pytest

from app.answers.service import AnswerService
from app.llm.service import ModelService
from app.queries.service import QueryService
from scripts.answer_evaluation_dataset import load_answer_evaluation
from scripts.dataset_manifest import digest, load_manifest
from scripts.evaluate_answers import automatic_checks, evaluate_answers, main, write_report
from scripts.query_evaluation_dataset import load_evaluation, resolve_case
from tests.app.queries import conftest as query_fixtures
from tests.app.queries.test_service import FakeProvider

query_data = query_fixtures.query_data


@pytest.fixture
def fixed_report():
    return evaluate_answers(
        load_evaluation(), load_answer_evaluation(), load_manifest(), UUID(int=1)
    )


def test_fixed_report_is_complete_but_does_not_claim_semantic_acceptance(fixed_report):
    assert len(fixed_report.cases) == 24
    assert all(all(c.checks.values()) for c in fixed_report.cases)
    assert fixed_report.review_status == "not_measured"
    assert fixed_report.mode == "fixed_evidence"
    assert fixed_report.model_id is None and fixed_report.max_attempts == 0
    assert all(c.events == () for c in fixed_report.cases)


def test_output_never_defaults_unmeasured_facts_to_pass(tmp_path, fixed_report):
    write_report(tmp_path, fixed_report, load_answer_evaluation())
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["reviewer"] is None
    assert all(c["unsupported_claims"] is None for c in review["cases"])
    assert all(all(f is None for f in c["required_facts_covered"]) for c in review["cases"])
    assert review["report_sha256"] == digest(fixed_report.model_dump(mode="json"))
    assert "Expected evidence:" in (tmp_path / "review.md").read_text()


def test_default_cli_does_not_construct_database_or_provider(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No external calls allowed")

    monkeypatch.setattr("scripts.evaluate_answers.Database", forbidden)
    monkeypatch.setattr("scripts.evaluate_answers.configured_provider", forbidden)
    folder = tmp_path / "run"
    assert main(["--output", str(folder)]) == 0
    assert len((folder / "cases.jsonl").read_text().splitlines()) == 24
    before = (folder / "report.json").read_bytes()
    assert main(["--output", str(folder)]) == 2
    assert (folder / "report.json").read_bytes() == before


def test_mechanical_checks_do_not_certify_prose(fixed_report):
    case = next(c for c in fixed_report.cases if c.key == "stock-at-reorder-point")
    wrong = case.turn.response.outcome.answer.model_copy(update={"text": "The quantity is 999."})
    turn = case.turn.model_copy(
        update={
            "response": case.turn.response.model_copy(
                update={"outcome": case.turn.response.outcome.model_copy(update={"answer": wrong})}
            )
        }
    )
    expected = resolve_case(
        next(c for c in load_evaluation().cases if c.key == case.key), load_manifest(), UUID(int=1)
    )
    assert all(automatic_checks(expected, turn, (), live=False).values())
    # Mechanical checks alone do not measure factual correctness.
    assert fixed_report.review_status == "not_measured"


def test_unsupported_prose_uuid_is_rejected(fixed_report):
    case = next(c for c in fixed_report.cases if c.key == "stock-at-reorder-point")
    wrong = case.turn.response.outcome.answer.model_copy(update={"text": str(uuid4())})
    turn = case.turn.model_copy(
        update={
            "response": case.turn.response.model_copy(
                update={"outcome": case.turn.response.outcome.model_copy(update={"answer": wrong})}
            )
        }
    )
    expected = resolve_case(
        next(c for c in load_evaluation().cases if c.key == case.key), load_manifest(), UUID(int=1)
    )
    assert not automatic_checks(expected, turn, (), live=False)["references"]
    assert not automatic_checks(expected, case.turn, (), live=True)["trace"]


@pytest.mark.integration
def test_live_workflow_is_one_attempt_per_case_with_exact_scope_review(query_data):
    database, _, manifest, workspaces, _, _ = query_data
    queries, answers = load_evaluation(), load_answer_evaluation()
    expected = [resolve_case(c, manifest, workspaces[0]) for c in queries.cases]

    class SequenceProvider(FakeProvider):
        def generate(self, request):
            self.output = expected[len(self.requests)].expected_plan.model_dump_json()
            return super().generate(request)

    provider = SequenceProvider("")
    service = AnswerService(QueryService(database, ModelService(provider, max_attempts=1), "test"))
    report = evaluate_answers(queries, answers, manifest, workspaces[0], service, model_id="test")
    assert all(all(c.checks.values()) for c in report.cases)
    assert len(provider.requests) == 24
    assert report.mode == "live_scope_confirmation"
    assert all(c.turn for c in report.cases)


def test_fresh_holdout_preserves_intents_but_changes_wording():
    from scripts.evaluate_answers import ROOT

    queries = load_evaluation(ROOT / "data/evaluations/queries-holdout-3.json")
    answers = load_answer_evaluation(
        ROOT / "data/evaluations/answers-holdout-1.json",
        query_path=ROOT / "data/evaluations/queries-holdout-3.json",
    )
    report = evaluate_answers(queries, answers, load_manifest(), UUID(int=1))
    assert len(report.cases) == 24 and all(all(c.checks.values()) for c in report.cases)
    for original, fresh in zip(load_evaluation().cases, queries.cases, strict=True):
        assert original.question != fresh.question
        a = resolve_case(original, load_manifest(), UUID(int=1))
        b = resolve_case(fresh, load_manifest(), UUID(int=1))
        assert a.expected_plan == b.expected_plan and a.expected_result == b.expected_result


def test_all_unsupported_claim_challenges_have_no_prose_delivery_input():
    from pydantic import ValidationError

    from app.answers.contracts import FactSelection

    for challenge in load_answer_evaluation().challenges:
        with pytest.raises(ValidationError):
            FactSelection.model_validate({"fact_ids": [], "text": challenge.candidate_claim})
