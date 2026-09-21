import json
import logging
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.answers.contracts import AnswerTurn
from app.answers.service import AnswerService
from app.database import Database
from app.llm.errors import ModelErrorKind
from app.llm.service import ModelService
from app.queries.contracts import QueryPageRequest
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.service import QueryService
from scripts.query_evaluation_dataset import SupportedCase, load_evaluation, resolve_case
from tests.app.answers.test_validation import change_request, request_for
from tests.app.queries import conftest as query_fixtures
from tests.app.queries.test_service import FakeProvider, context

query_data = query_fixtures.query_data
CASES = load_evaluation().cases


def subject_for(request):
    queries = Mock(spec=QueryService)
    queries.ask.return_value = request.query
    return AnswerService(queries), queries


def answer_events(caplog):
    return [json.loads(r.message) for r in caplog.records if r.name == "app.answers.service"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "case", [c for c in CASES if isinstance(c, SupportedCase)], ids=lambda c: c.key
)
def test_question_to_database_to_answer_in_two_workspaces(query_data, case, caplog):
    database, _, manifest, workspaces, _, _ = query_data
    for workspace in workspaces:
        expected = resolve_case(case, manifest, workspace)
        provider = FakeProvider(expected.expected_plan.model_dump_json())
        subject = AnswerService(
            QueryService(database, ModelService(provider, max_attempts=1), "test-model")
        )
        ctx = context(workspace)
        with caplog.at_level(logging.INFO):
            turn = subject.ask(ctx, expected.question, QueryPageRequest(limit=100))
            if turn.request.query.scope_status == "awaiting_confirmation":
                assert turn.response.outcome.reason == "awaiting_confirmation"
                assert turn.request.query.response is None
                previous_id = turn.response.synthesis_operation_id
                turn = subject.confirm_scope(ctx, turn, expected.expected_plan)
                assert any(
                    e.get("previous_synthesis_operation_id") == str(previous_id)
                    for e in answer_events(caplog)
                )
        assert len(provider.requests) == 1  # No ordering/synthesis/confirmation model call.
        assert turn.request.query.response.result == expected.expected_result
        assert turn.response.context == ctx
        assert turn.request.question == expected.question
        assert AnswerTurn.model_validate_json(turn.model_dump_json()) == turn
        result = turn.response.outcome
        assert result.status == (
            "cautious" if expected.expected_result.page.total == 0 else "answered"
        )
        if result.status == "cautious":
            assert result.reason == "no_results"
        else:
            assert result.coverage == "complete"
            assert result.answer.text not in caplog.text
        events = answer_events(caplog)
        assert [e["event"] for e in events[-2:]] == ["answer_render", "answer_operation"]
        for event in events[-2:]:
            assert event["request_id"] == str(ctx.request_id)
            assert event["query_operation_id"] == str(ctx.operation_id)
            assert event["operation_id"] == str(turn.response.synthesis_operation_id)
            assert event["planning_operation_id"] == str(turn.request.query.planning_operation_id)
            assert event["resolution_operation_id"] == str(
                turn.request.query.resolution_operation_id
            )
            assert event["rows"] == len(expected.expected_result.page.rows)
        assert expected.question not in caplog.text
        assert str(workspace) not in caplog.text
        assert expected.expected_result.model_dump_json() not in caplog.text
        caplog.clear()


@pytest.mark.parametrize(
    "case", [c for c in CASES if not isinstance(c, SupportedCase)], ids=lambda c: c.key
)
def test_declines_are_cautious_without_execution_or_a_second_model_call(case):
    database = Mock(spec=Database)
    provider = FakeProvider(case.expected.model_dump_json())
    subject = AnswerService(QueryService(database, ModelService(provider, max_attempts=1), "test"))
    turn = subject.ask(context(), case.question)
    assert turn.response.outcome.reason == "declined"
    assert turn.request.query.response is None
    assert len(provider.requests) == 1
    database.query_session.assert_not_called()


@pytest.mark.parametrize("kind", list(QueryErrorKind))
def test_query_failures_propagate_without_empty_answers_or_content_logging(kind, caplog):
    request = request_for()
    subject, queries = subject_for(request)
    error = QueryError(request.query.context, kind)
    queries.ask.side_effect = error
    with caplog.at_level(logging.INFO), pytest.raises(QueryError) as caught:
        subject.ask(request.query.context, "PRIVATE QUESTION")
    assert caught.value is error
    events = answer_events(caplog)
    assert len(events) == 1 and events[0]["event"] == "answer_operation"
    assert events[0]["error_kind"] == kind.value
    assert events[0]["outcome"] == "failed"
    assert "PRIVATE QUESTION" not in caplog.text


def test_actual_planning_failure_has_correlated_answer_failure(caplog):
    database = Mock(spec=Database)
    provider = FakeProvider("private output", error=ModelErrorKind.TIMEOUT)
    subject = AnswerService(QueryService(database, ModelService(provider, max_attempts=1), "test"))
    ctx = context()
    with caplog.at_level(logging.INFO), pytest.raises(QueryError, match="model_failure"):
        subject.ask(ctx, "private question")
    assert len(provider.requests) == 1
    assert answer_events(caplog)[0]["query_operation_id"] == str(ctx.operation_id)
    assert "private question" not in caplog.text and "private output" not in caplog.text


@pytest.mark.parametrize("field", ["request_id", "operation_id", "workspace_id"])
def test_confirmation_cannot_cross_context(field):
    request = change_request(
        request_for("q1-positive-unrelated-and-deduplicated"),
        lambda q: q.update(scope_status="awaiting_confirmation", response=None),
    )
    subject, queries = subject_for(request)
    pending = subject.ask(request.query.context, request.question)
    wrong = request.query.context.model_copy(update={field: uuid4()})
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.confirm_scope(wrong, pending, request.query.plan)
    queries.confirm_scope.assert_not_called()


def test_confirmation_rejects_nonpending_and_forged_responses():
    request = request_for()
    subject, queries = subject_for(request)
    turn = subject.ask(request.query.context, request.question)
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.confirm_scope(request.query.context, turn, request.query.plan)
    queries.confirm_scope.assert_not_called()
    forged = turn.model_copy(
        update={"response": turn.response.model_copy(update={"context": context()})}
    )
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.confirm_scope(request.query.context, forged, request.query.plan)


def test_exact_plan_guard_remains_in_query_service():
    request = change_request(
        request_for("q1-positive-unrelated-and-deduplicated"),
        lambda q: q.update(scope_status="awaiting_confirmation", response=None),
    )
    stub, _ = subject_for(request)
    pending = stub.ask(request.query.context, request.question)
    database = Mock(spec=Database)
    provider = FakeProvider("unused")
    real = AnswerService(QueryService(database, ModelService(provider), "test"))
    wrong_plan = request.query.plan.model_copy(update={"unit_statuses": ("operational",)})
    with pytest.raises(QueryError, match="invalid_plan"):
        real.confirm_scope(request.query.context, pending, wrong_plan)
    assert provider.requests == []
    database.query_session.assert_not_called()


@pytest.mark.parametrize("offset,count", [(0, 1), (4, 0)])
def test_pagination_is_forwarded_and_rendering_preserves_partial_or_empty_page(offset, count):
    request = request_for("q3-active-boundaries-and-distinct-targets")

    def mutate(q):
        p = q["response"]["result"]["page"]
        p.update(offset=offset, limit=1, rows=p["rows"][offset : offset + count])
        q["page_request"] = {"offset": offset, "limit": 1}

    request = change_request(request, mutate)
    subject, queries = subject_for(request)
    page = QueryPageRequest(limit=1, offset=offset)
    turn = subject.ask(request.query.context, request.question, page)
    queries.ask.assert_called_once_with(request.query.context, request.question, page)
    if count:
        assert turn.response.outcome.coverage == "partial"
    else:
        assert turn.response.outcome.reason == "insufficient_evidence"


def test_render_failure_has_safe_trace_and_is_not_an_empty_answer(monkeypatch, caplog):
    request = request_for()
    subject, _ = subject_for(request)

    def fail(_):
        raise RuntimeError("private rendering details")

    monkeypatch.setattr("app.answers.service.render_answer", fail)
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
        subject.ask(request.query.context, request.question)
    events = answer_events(caplog)
    assert [e["event"] for e in events] == ["answer_render", "answer_operation"]
    assert all(e["error_kind"] == "internal_error" for e in events)
    assert "private rendering details" not in caplog.text


def test_success_telemetry_has_only_documented_metadata(caplog):
    request = request_for()
    subject, _ = subject_for(request)
    with caplog.at_level(logging.INFO):
        subject.ask(request.query.context, request.question)
    allowed = {
        "event",
        "request_id",
        "operation_id",
        "query_operation_id",
        "renderer_version",
        "duration_ms",
        "outcome",
        "error_kind",
        "planning_operation_id",
        "resolution_operation_id",
        "operation",
        "scope_status",
        "answer_status",
        "rows",
        "total",
        "coverage",
        "references",
    }
    for event in answer_events(caplog):
        assert set(event) == allowed


def test_query_result_cannot_cross_the_callers_context():
    request = request_for()
    subject, _ = subject_for(request)
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.ask(context(), request.question)


def test_oversized_answer_is_withheld_and_traced(caplog):
    request = request_for("completed-work")

    def mutate(q):
        page = q["response"]["result"]["page"]
        row = page["rows"][0]
        page.update(total=100, rows=[{**row, "work_order_id": str(uuid4())} for _ in range(100)])

    request = change_request(request, mutate)
    subject, _ = subject_for(request)
    with caplog.at_level(logging.INFO):
        turn = subject.ask(request.query.context, request.question)
    assert turn.response.outcome.reason == "invalid_answer"
    assert all(e["reason"] == "invalid_answer" for e in answer_events(caplog))
