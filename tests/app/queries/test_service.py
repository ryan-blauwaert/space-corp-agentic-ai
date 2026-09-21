import json
import logging
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.database import Database
from app.llm.contracts import ModelFinishReason, ModelResponse
from app.llm.errors import ModelCallError, ModelErrorKind
from app.llm.provider import ModelProvider
from app.llm.service import ModelService
from app.queries.contracts import DeclinedPlan, QueryContext, QueryPageRequest
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.service import QueryService
from scripts.query_evaluation_dataset import SupportedCase, load_evaluation, resolve_case


class FakeProvider(ModelProvider):
    def __init__(self, output, *, finish=ModelFinishReason.COMPLETED, error=None):
        self.output, self.finish, self.error = output, finish, error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error:
            raise ModelCallError(request.context, self.error)
        return ModelResponse(context=request.context, text=self.output, finish_reason=self.finish)


def context(workspace=None):
    return QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace or uuid4())


def service(database, output, **kwargs):
    provider = FakeProvider(output, **kwargs)
    return QueryService(database, ModelService(provider, max_attempts=1), "test-model"), provider


@pytest.mark.parametrize("question", ["", "  ", "a" * 4001, None])
def test_invalid_question_does_not_call_model_or_database(question):
    database = Mock(spec=Database)
    subject, provider = service(database, "unused")
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.ask(context(), question)
    assert not provider.requests
    database.query_session.assert_not_called()


def test_forged_page_rejected_before_model_call():
    subject, provider = service(Mock(spec=Database), "unused")
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.ask(context(), "stock", QueryPageRequest.model_construct(limit=999))
    assert not provider.requests


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_model_failures_are_safe_and_do_not_execute(kind, caplog):
    database = Mock(spec=Database)
    subject, _ = service(database, "secret", error=kind)
    with caplog.at_level(logging.INFO), pytest.raises(QueryError, match="model_failure"):
        subject.ask(context(), "private question")
    database.query_session.assert_not_called()
    assert "private question" not in caplog.text
    assert "secret" not in caplog.text
    assert '"event":"query_planning"' in caplog.text


@pytest.mark.parametrize(
    "output,finish,kind",
    [
        ('{"operation":"inventory"}', ModelFinishReason.OUTPUT_LIMIT, "model_failure"),
        ('{"operation":"inventory","sql":"secret"}', ModelFinishReason.COMPLETED, "invalid_plan"),
    ],
)
def test_invalid_or_truncated_output_never_executes(output, finish, kind):
    database = Mock(spec=Database)
    subject, _ = service(database, output, finish=finish)
    with pytest.raises(QueryError, match=kind):
        subject.ask(context(), "stock")
    database.query_session.assert_not_called()


CASES = load_evaluation().cases


@pytest.mark.parametrize(
    "case", [c for c in CASES if not isinstance(c, SupportedCase)], ids=lambda c: c.key
)
def test_declined_fixtures_never_open_database(case, caplog):
    database = Mock(spec=Database)
    # A canned response tests application handling, not a model's classification accuracy.
    output = json.dumps({"operation": "declined", "reason": case.expected.reason})
    subject, provider = service(database, output)
    with caplog.at_level(logging.INFO):
        outcome = subject.ask(context(), case.question)
    assert isinstance(outcome.plan, DeclinedPlan)
    assert outcome.response is None
    assert len(provider.requests) == 1
    database.query_session.assert_not_called()
    assert "query_execution" not in caplog.text


@pytest.mark.integration
@pytest.mark.parametrize(
    "case", [c for c in CASES if isinstance(c, SupportedCase)], ids=lambda c: c.key
)
def test_supported_fixtures_complete_model_to_database_path(query_data, case, caplog):
    database, _, manifest, workspaces, _, _ = query_data
    for workspace in workspaces:
        expected = resolve_case(case, manifest, workspace)
        subject, provider = service(database, expected.expected_plan.model_dump_json())
        ctx = context(workspace)
        with caplog.at_level(logging.INFO):
            outcome = subject.ask(ctx, expected.question, QueryPageRequest(limit=100))
            if outcome.scope_status == "awaiting_confirmation":
                assert outcome.response is None
                outcome = subject.confirm_scope(ctx, outcome, expected.expected_plan)
        assert outcome.plan == expected.expected_plan
        assert outcome.response.result == expected.expected_result
        assert outcome.response.context == ctx
        assert len(provider.requests) == 1
        request = provider.requests[0]
        assert request.context.operation_id == outcome.planning_operation_id
        assert request.context.request_id == ctx.request_id
        assert request.max_output_tokens == 4096
        assert request.timeout_seconds == 30.0
        assert (
            len({outcome.planning_operation_id, outcome.resolution_operation_id, ctx.operation_id})
            == 3
        )
        events = [json.loads(r.message) for r in caplog.records if r.name == "app.queries.service"]
        assert [
            e["event"] for e in events if e["event"] not in ("query_grounding", "query_scope")
        ] == [
            "query_planning",
            "query_resolution",
            "query_execution",
        ]
        assert all(e["request_id"] == str(ctx.request_id) for e in events[-3:])
        assert all(e["query_operation_id"] == str(ctx.operation_id) for e in events[-3:])
        assert expected.question not in caplog.text
        assert str(workspace) not in caplog.text
        assert outcome.response.result.model_dump_json() not in caplog.text
        caplog.clear()


def test_execution_failure_has_safe_correlated_trace(caplog):
    database = Mock(spec=Database)
    subject, _ = service(database, '{"operation":"inventory"}')
    ctx = context()
    subject.operations = Mock()
    subject.operations.execute.side_effect = QueryError(ctx, QueryErrorKind.DATABASE_UNAVAILABLE)
    with caplog.at_level(logging.INFO), pytest.raises(QueryError, match="database_unavailable"):
        proposal = subject.ask(ctx, "private question")
        subject.confirm_scope(ctx, proposal, proposal.plan)
    events = [json.loads(r.message) for r in caplog.records if r.name == "app.queries.service"]
    assert events[-1]["event"] == "query_execution"
    assert events[-1]["operation_id"] == str(ctx.operation_id)
    assert events[-1]["outcome"] == "failed"
    assert events[-1]["error_kind"] == "database_unavailable"
    assert "private question" not in caplog.text


def test_unexpected_provider_error_is_traced_without_exception_contents(caplog):
    subject, _ = service(Mock(spec=Database), "unused")
    subject.model = Mock()
    subject.model.generate.side_effect = RuntimeError("secret provider payload")
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
        subject.ask(context(), "private question")
    assert "secret provider payload" not in caplog.text
    assert '"error_kind":"internal_error"' in caplog.text


def test_bad_shape_does_not_resolve_even_a_valid_literal_reference():
    database = Mock(spec=Database)
    output = '{"operation":"inventory","component_id":"C01","sql":"SELECT secret"}'
    subject, _ = service(database, output)
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.ask(context(), "C01")
    database.query_session.assert_not_called()


def test_grounding_failure_prevents_model_call_and_has_safe_trace(monkeypatch, caplog):
    ctx = context()
    subject, provider = service(Mock(spec=Database), "unused")
    monkeypatch.setattr(
        "app.queries.service.ground_references",
        Mock(side_effect=QueryError(ctx, QueryErrorKind.DATABASE_UNAVAILABLE)),
    )
    with caplog.at_level(logging.INFO), pytest.raises(QueryError, match="database_unavailable"):
        subject.ask(ctx, "private question")
    assert not provider.requests
    events = [json.loads(r.message) for r in caplog.records if r.name == "app.queries.service"]
    assert [event["event"] for event in events] == ["query_grounding"]
    assert events[0]["error_kind"] == "database_unavailable"
    assert "private question" not in caplog.text


@pytest.mark.parametrize(
    "proposal",
    [
        {"operation": "inventory", "below_reorder_point": True},
        {"operation": "inventory", "facility": {"facility_type": "lunar_installation"}},
        {"operation": "incidents", "fault_code": "BLOWER"},
        {"operation": "facility_equipment", "unit_statuses": ["offline"]},
        {"operation": "work_orders", "as_of": "2026-01-31T12:00:00Z"},
    ],
)
def test_unanchored_proposal_never_executes_without_exact_plan_confirmation(proposal, caplog):
    database = Mock(spec=Database)
    subject, provider = service(database, json.dumps(proposal))
    subject.operations = Mock()
    subject.equipment = Mock()
    with caplog.at_level(logging.INFO):
        pending = subject.ask(
            context(), "Records with BLOWER fault", QueryPageRequest(limit=7, offset=2)
        )
    assert pending.scope_status == "awaiting_confirmation"
    assert pending.response is None
    assert pending.page_request == QueryPageRequest(limit=7, offset=2)
    subject.operations.execute.assert_not_called()
    subject.equipment.execute.assert_not_called()
    database.query_session.assert_not_called()
    assert len(provider.requests) == 1
    assert '"outcome":"awaiting_confirmation"' in caplog.text
    assert "query_execution" not in caplog.text


@pytest.mark.parametrize(
    "fault", ["workspace", "request", "operation", "plan", "page", "not_pending", "declined"]
)
def test_scope_confirmation_rejects_changed_approval_or_context_before_execution(fault):
    from app.queries.contracts import InventoryPlan

    subject, provider = service(Mock(spec=Database), '{"operation":"inventory"}')
    ctx = context()
    pending = subject.ask(ctx, "Show stock")
    approved = pending.plan
    if fault in ("workspace", "request", "operation"):
        ctx = ctx.model_copy(update={fault + "_id": uuid4()})
    elif fault == "plan":
        approved = InventoryPlan(operation="inventory", below_reorder_point=True)
    elif fault == "page":
        pending = pending.model_copy(
            update={"page_request": QueryPageRequest.model_construct(limit=999)}
        )
    elif fault == "not_pending":
        pending = pending.model_copy(update={"scope_status": "confirmed"})
    else:
        pending = pending.model_copy(
            update={"plan": DeclinedPlan(operation="declined", reason="missing_input")}
        )
    subject.operations = Mock()
    with pytest.raises(QueryError, match="invalid_plan"):
        subject.confirm_scope(ctx, pending, approved)
    subject.operations.execute.assert_not_called()
    assert len(provider.requests) == 1


@pytest.mark.parametrize(
    "proposal,requires_review",
    [
        ({"operation": "inventory"}, True),
        ({"operation": "incidents", "equipment_model_id": str(uuid4())}, True),
        ({"operation": "inventory", "component_id": str(uuid4())}, True),
        ({"operation": "inventory", "facility": {"location": "Hangar"}}, True),
        ({"operation": "inventory", "facility": {"facility_id": str(uuid4())}}, False),
        ({"operation": "incidents", "equipment_unit_id": str(uuid4())}, False),
        ({"operation": "compatible_stock", "equipment_unit_id": str(uuid4())}, False),
        (
            {
                "operation": "work_orders",
                "as_of": "2026-01-31T12:00:00Z",
                "originating_incident_id": str(uuid4()),
            },
            False,
        ),
        (
            {
                "operation": "work_orders",
                "as_of": "2026-01-31T12:00:00Z",
                "target_equipment_unit_id": str(uuid4()),
            },
            False,
        ),
    ],
)
def test_scope_gate_uses_typed_anchors_not_question_phrases(proposal, requires_review):
    from app.queries.contracts import QUERY_PLAN
    from app.queries.service import needs_scope_confirmation

    assert needs_scope_confirmation(QUERY_PLAN.validate_python(proposal)) is requires_review
