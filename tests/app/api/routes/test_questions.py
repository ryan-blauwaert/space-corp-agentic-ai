import json
import logging
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.answers.service import AnswerService
from app.api.dependencies import get_answer_service
from app.api.pending_answers import PendingAnswers, PendingAnswerUnavailable
from app.config import Settings
from app.llm.service import ModelService
from app.main import create_app
from app.queries.contracts import QUERY_RESULT, QueryResponse
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.service import QueryOutcome, QueryService
from scripts.query_evaluation_dataset import (
    SupportedCase,
    evidence_matches,
    load_evaluation,
    resolve_case,
)
from tests.app.answers.test_validation import request_for
from tests.app.api.test_pending_answers import pending_turn
from tests.app.queries import conftest as query_fixtures
from tests.app.queries.test_service import FakeProvider

query_data = query_fixtures.query_data


@pytest.fixture
def api():
    application = create_app(Settings(_env_file=None, default_workspace_id=uuid4()), MagicMock())
    queries = Mock(spec=QueryService)
    answers = AnswerService(queries)
    application.dependency_overrides[get_answer_service] = lambda: answers
    with TestClient(application) as client:
        yield client, queries


def arrange(queries, key="stock-at-reorder-point", pending=False):
    original = request_for(key).query

    def ask(context, question, page):
        payload = original.model_dump(mode="json")
        payload.update(context=context.model_dump(mode="json"), page_request=page.model_dump())
        if pending:
            payload.update(scope_status="awaiting_confirmation", response=None)
        elif payload["response"]:
            payload["response"]["context"] = context.model_dump(mode="json")
        return QueryOutcome.model_validate(payload)

    def confirm(context, proposal, plan):
        assert plan == proposal.plan == original.plan
        assert proposal.response is None
        return proposal.model_copy(
            update={
                "scope_status": "confirmed",
                "response": QueryResponse(
                    context=context,
                    catalog_release_id=original.response.catalog_release_id,
                    result=original.response.result,
                ),
            }
        )

    queries.ask.side_effect = ask
    queries.confirm_scope.side_effect = confirm


def test_answer_has_evidence_safe_public_context_and_trace_linkage(api, caplog):
    client, queries = api
    arrange(queries)
    with caplog.at_level(logging.INFO):
        response = client.post("/questions", json={"question": "PRIVATE QUESTION"})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"]["status"] == "answered"
    assert body["outcome"]["answer"]["references"]
    assert body["evidence"]["operation"] == "inventory"
    assert body["confirmation"] is None
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == body["request_id"]
    assert "workspace_id" not in response.text and "PRIVATE QUESTION" not in response.text
    assert "PRIVATE QUESTION" not in caplog.text
    events = [json.loads(r.message) for r in caplog.records if r.name == "app.answers.service"]
    assert all(e["request_id"] == body["request_id"] for e in events)
    context = queries.ask.call_args.args[0]
    assert context.workspace_id == client.app.state.settings.default_workspace_id
    assert str(context.operation_id) == body["query_operation_id"]


def test_confirmation_executes_retained_plan_once_without_replanning(api):
    client, queries = api
    arrange(queries, pending=True)
    first = client.post("/questions", json={"question": "stock"}).json()
    assert first["outcome"]["reason"] == "awaiting_confirmation"
    assert first["evidence"] is None
    queries.confirm_scope.assert_not_called()
    token = first["confirmation"]["confirmation_id"]
    assert first["confirmation"]["expires_in_seconds"] == 300
    response = client.post("/questions/confirm", json={"confirmation_id": token})
    assert response.status_code == 200
    final = response.json()
    assert final["scope_status"] == "confirmed" and final["confirmation"] is None
    assert final["request_id"] == first["request_id"]
    assert final["query_operation_id"] == first["query_operation_id"]
    assert final["synthesis_operation_id"] != first["synthesis_operation_id"]
    assert final["plan"] == first["plan"]
    assert queries.ask.call_count == queries.confirm_scope.call_count == 1
    assert client.post("/questions/confirm", json={"confirmation_id": token}).status_code == 404
    assert queries.confirm_scope.call_count == 1


@pytest.mark.parametrize("mode", ["unknown", "expired", "workspace", "restart"])
def test_unavailable_confirmation_never_executes(api, mode):
    client, queries = api
    clock = Mock(return_value=0)
    client.app.state.pending_answers = PendingAnswers(clock=clock)
    arrange(queries, pending=True)
    first = client.post("/questions", json={"question": "stock"}).json()
    token = first["confirmation"]["confirmation_id"]
    if mode == "unknown":
        token = "x" * 43
    elif mode == "expired":
        clock.return_value = 300
    elif mode == "workspace":
        client.app.state.settings.default_workspace_id = uuid4()
    else:
        client.app.state.pending_answers = PendingAnswers()
    result = client.post("/questions/confirm", json={"confirmation_id": token})
    assert result.status_code == 404
    assert result.headers["content-type"] == "application/problem+json"
    assert token not in result.text
    queries.confirm_scope.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 4001},
        {"question": 1},
        {"question": "stock", "workspace_id": str(uuid4())},
        {"question": "stock", "plan": {}},
        {"question": "stock", "page": {"limit": 101}},
        {"question": "stock", "page": {"offset": -1}},
        {"question": "stock", "page": {"limit": True}},
        {"question": "stock", "page": {"workspace_id": str(uuid4())}},
    ],
)
def test_request_validation_never_plans(api, body):
    client, queries = api
    assert client.post("/questions", json=body).status_code == 422
    queries.ask.assert_not_called()


@pytest.mark.parametrize("extra", ["plan", "page", "workspace_id", "pending", "question"])
def test_confirmation_cannot_supply_authority_or_change_plan(api, extra):
    client, queries = api
    arrange(queries, pending=True)
    token = client.post("/questions", json={"question": "stock"}).json()["confirmation"][
        "confirmation_id"
    ]
    assert (
        client.post("/questions/confirm", json={"confirmation_id": token, extra: {}}).status_code
        == 422
    )
    queries.confirm_scope.assert_not_called()
    assert client.post("/questions/confirm", json={"confirmation_id": token}).status_code == 200


@pytest.mark.parametrize(
    "kind,code",
    [
        (QueryErrorKind.INVALID_PLAN, 502),
        (QueryErrorKind.NOT_FOUND, 404),
        (QueryErrorKind.MODEL_FAILURE, 503),
        (QueryErrorKind.DATABASE_UNAVAILABLE, 503),
        (QueryErrorKind.TIMEOUT, 504),
        (QueryErrorKind.RESOURCE_LIMIT, 400),
    ],
)
def test_query_errors_are_safe_problems(api, kind, code):
    client, queries = api

    def fail(context, *_):
        raise QueryError(context, kind)

    queries.ask.side_effect = fail
    result = client.post("/questions", json={"question": "PRIVATE QUESTION"})
    assert result.status_code == code
    assert result.headers["content-type"] == "application/problem+json"
    assert result.json()["status"] == code
    assert "PRIVATE QUESTION" not in result.text
    assert UUID(result.headers["x-request-id"])


def test_failed_confirmation_stays_consumed(api):
    client, queries = api
    arrange(queries, pending=True)
    token = client.post("/questions", json={"question": "stock"}).json()["confirmation"][
        "confirmation_id"
    ]
    queries.confirm_scope.side_effect = RuntimeError("PRIVATE INTERNAL DETAILS")
    response = client.post("/questions/confirm", json={"confirmation_id": token})
    assert response.status_code == 500 and "PRIVATE" not in response.text
    assert client.post("/questions/confirm", json={"confirmation_id": token}).status_code == 404
    assert queries.confirm_scope.call_count == 1


def test_pending_capacity_returns_safe_failure(api):
    client, queries = api
    client.app.state.pending_answers = PendingAnswers(capacity=1)
    arrange(queries, pending=True)
    first = client.post("/questions", json={"question": "stock"}).json()
    assert client.post("/questions", json={"question": "stock"}).status_code == 503
    assert (
        client.post(
            "/questions/confirm", json={"confirmation_id": first["confirmation"]["confirmation_id"]}
        ).status_code
        == 200
    )


@pytest.mark.parametrize("offset,reason", [(0, None), (10, "insufficient_evidence")])
def test_page_is_preserved_through_confirmation(api, offset, reason):
    client, queries = api
    arrange(queries, "q3-active-boundaries-and-distinct-targets", pending=True)
    confirm = queries.confirm_scope.side_effect

    def limited(context, proposal, plan):
        turn = confirm(context, proposal, plan)
        data = turn.model_dump(mode="json")
        page = data["response"]["result"]["page"]
        page.update(limit=1, offset=offset, rows=page["rows"][offset : offset + 1])
        return QueryOutcome.model_validate(data)

    queries.confirm_scope.side_effect = limited
    first = client.post(
        "/questions", json={"question": "work", "page": {"limit": 1, "offset": offset}}
    ).json()
    body = client.post(
        "/questions/confirm", json={"confirmation_id": first["confirmation"]["confirmation_id"]}
    ).json()
    assert body["page"] == first["page"] == {"limit": 1, "offset": offset}
    if reason:
        assert body["outcome"]["reason"] == reason
    else:
        assert body["outcome"]["coverage"] == "partial"


def test_lifespan_discards_pending_questions():
    application = create_app(Settings(_env_file=None, default_workspace_id=uuid4()), MagicMock())
    turn = pending_turn()
    with TestClient(application):
        token = application.state.pending_answers.add(turn)
    with pytest.raises(PendingAnswerUnavailable):
        application.state.pending_answers.take(token, turn.request.query.context.workspace_id)


def test_missing_model_configuration_keeps_reads_available():
    application = create_app(
        Settings(_env_file=None, default_workspace_id=uuid4(), llm_api_key=None), MagicMock()
    )
    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        response = client.post("/questions", json={"question": "stock"})
        assert response.status_code == 503
        assert response.json()["detail"] == "Question planning is not configured."


@pytest.mark.parametrize("fail", [False, True])
def test_request_owned_provider_is_closed_on_success_and_failure(monkeypatch, fail):
    provider = FakeProvider('{"operation":"declined","reason":"unsupported_question"}')
    closed = []

    @contextmanager
    def configured(settings):
        assert settings.llm_model_id == "gpt-5.6-luna"
        assert settings.llm_reasoning_effort == "medium"
        try:
            yield provider
        finally:
            closed.append(True)

    monkeypatch.setattr("app.api.dependencies.configured_provider", configured)
    if fail:
        provider.generate = Mock(side_effect=RuntimeError("PRIVATE"))
    application = create_app(
        Settings(
            _env_file=None,
            default_workspace_id=uuid4(),
            llm_model_id="gpt-5.6-luna",
            llm_reasoning_effort="medium",
            llm_api_key="fake-key",
        ),
        MagicMock(),
    )
    with TestClient(application) as client:
        result = client.post("/questions", json={"question": "hello"})
        assert result.status_code == (500 if fail else 200)
    assert closed == [True]
    assert "PRIVATE" not in result.text and "fake-key" not in result.text


def test_openapi_and_documentation_cover_public_contract(api):
    client, _ = api
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200
    schema = client.get("/openapi.json").json()
    for path, operation_id in [
        ("/questions", "askQuestion"),
        ("/questions/confirm", "confirmQuestionScope"),
    ]:
        operation = schema["paths"][path]["post"]
        assert operation["operationId"] == operation_id
        assert operation["tags"] == ["questions"]
        assert "application/json" in operation["responses"]["422"]["content"]
        for code in (400, 404, 500, 502, 503, 504):
            assert "application/problem+json" in operation["responses"][str(code)]["content"]
    assert "workspace_id" not in schema["components"]["schemas"]["QuestionRequest"]["properties"]
    assert schema["components"]["schemas"]["QuestionRequest"]["additionalProperties"] is False


@pytest.mark.integration
@pytest.mark.parametrize("case", load_evaluation().cases, ids=lambda case: case.key)
def test_http_to_real_query_and_answer_in_two_workspaces(query_data, case):
    database, _, manifest, workspaces, _, _ = query_data
    for workspace in workspaces:
        expected = resolve_case(case, manifest, workspace)
        provider = FakeProvider(expected.expected_plan.model_dump_json())
        service = AnswerService(
            QueryService(database, ModelService(provider, max_attempts=1), "test")
        )
        application = create_app(Settings(_env_file=None, default_workspace_id=workspace), database)
        application.dependency_overrides[get_answer_service] = lambda: service
        with TestClient(application) as client:
            response = client.post(
                "/questions", json={"question": expected.question, "page": {"limit": 100}}
            )
            assert response.status_code == 200, response.text
            body = response.json()
            if body["confirmation"]:
                assert body["evidence"] is None
                response = client.post(
                    "/questions/confirm",
                    json={"confirmation_id": body["confirmation"]["confirmation_id"]},
                )
                assert response.status_code == 200, response.text
                body = response.json()
            if isinstance(case, SupportedCase):
                assert evidence_matches(
                    QUERY_RESULT.validate_python(body["evidence"]), expected.expected_result
                )
                if expected.expected_result.page.total == 0:
                    assert body["outcome"]["reason"] == "no_results"
                else:
                    assert body["outcome"]["status"] == "answered"
                    assert body["outcome"]["coverage"] == "complete"
            else:
                assert body["evidence"] is None
                assert body["outcome"]["reason"] == "declined"
            assert len(provider.requests) == 1
