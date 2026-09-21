import json
from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.config import Settings
from app.facilities.models import FacilityRecord
from app.llm.contracts import ModelResponse
from app.llm.provider import ModelProvider
from app.llm.service import ModelService
from app.queries.contracts import DeclinedPlan, QueryContext, QueryResponse
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.service import QueryOutcome, QueryService
from scripts import evaluate_queries as runner
from scripts.dataset_manifest import load_manifest
from scripts.query_evaluation_dataset import load_evaluation, resolve_case
from tests.app.queries import conftest as query_fixtures

query_data = query_fixtures.query_data


class FixtureProvider(ModelProvider):
    def __init__(self, cases):
        self.cases = iter(cases)
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        case = next(self.cases)
        # Expectations are test-only provider behavior; not supplied by the runner.
        assert case.question in json.loads(
            request.prompt.split("Untrusted question (JSON string):\n")[1]
        )
        return ModelResponse(
            context=request.context,
            text=case.expected_plan.model_dump_json(),
            finish_reason="completed",
            returned_model_id="test-revision",
        )


def fixture_case(index=0):
    manifest = load_manifest()
    dataset = load_evaluation()
    workspace = uuid4()
    return resolve_case(dataset.cases[index], manifest, workspace), workspace


def outcome(case, workspace):
    return QueryOutcome(
        context=QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace),
        planning_operation_id=uuid4(),
        resolution_operation_id=uuid4(),
        plan=case.expected_plan,
        response=QueryResponse(
            context=QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace),
            catalog_release_id=uuid4(),
            result=case.expected_result,
        )
        if case.expected_result
        else None,
    )


def test_scoring_accepts_semantically_unordered_status_selections():
    case, workspace = fixture_case()
    actual = outcome(case, workspace)
    actual = actual.model_copy(
        update={
            "plan": actual.plan.model_copy(
                update={"unit_statuses": tuple(reversed(actual.plan.unit_statuses))}
            )
        }
    )
    assert runner.score_case(case, actual, 1).passed


def test_wrong_intent_cannot_pass_with_correct_evidence():
    case, workspace = fixture_case()
    actual = outcome(case, workspace)
    actual = actual.model_copy(
        update={"plan": actual.plan.model_copy(update={"unit_statuses": None})}
    )
    score = runner.score_case(case, actual, 1)
    assert score.evidence_match and not score.intent_match and not score.passed


def test_wrong_evidence_cannot_pass_with_correct_intent():
    case, workspace = fixture_case()
    score = runner.score_case(
        case, outcome(case, workspace).model_copy(update={"response": None}), 1
    )
    assert score.intent_match and not score.evidence_match and not score.passed


def test_wrong_decline_reason_and_unexpected_execution_fail():
    case, workspace = fixture_case(-1)
    actual = outcome(case, workspace)
    wrong = actual.model_copy(
        update={"plan": DeclinedPlan(operation="declined", reason="unsupported_question")}
    )
    assert not runner.score_case(case, wrong, 1).passed
    supported, _ = fixture_case()
    wrong = actual.model_copy(update={"response": outcome(supported, workspace).response})
    score = runner.score_case(case, wrong, 1)
    assert not score.execution_policy_match and not score.passed


def test_errors_count_as_failures_and_do_not_leak_contents(capsys):
    manifest = load_manifest()
    dataset = load_evaluation()
    service = Mock(model_id="test-model")
    service.ask.side_effect = RuntimeError("SECRET payload")
    report = runner.evaluate(service, uuid4(), dataset, manifest, max_attempts=1)
    assert report.total == report.failed == 24 and report.passed == 0
    assert all(score.error_kind == "internal_error" for score in report.cases)
    assert "SECRET" not in report.model_dump_json() + capsys.readouterr().err


def test_safe_query_error_category_is_retained():
    case, workspace = fixture_case()
    ctx = outcome(case, workspace).context
    service = Mock(model_id="test-model")
    service.ask.side_effect = QueryError(ctx, QueryErrorKind.TIMEOUT)
    report = runner.evaluate(service, workspace, load_evaluation(), load_manifest(), max_attempts=1)
    assert all(score.error_kind == "timeout" for score in report.cases)


@pytest.mark.integration
@pytest.mark.parametrize(
    "fixture_name", ["queries-3.json", "queries-holdout-1.json", "queries-holdout-2.json"]
)
def test_complete_runner_with_real_restricted_database(query_data, capsys, fixture_name):
    database, _, manifest, workspaces, _, _ = query_data
    dataset = load_evaluation(runner.DEFAULT_EVALUATION.with_name(fixture_name))
    workspace = workspaces[0]
    cases = [resolve_case(case, manifest, workspace) for case in dataset.cases]
    runner.preflight(database, workspace, manifest, cases)
    provider = FixtureProvider(cases)
    report = runner.evaluate(
        QueryService(database, ModelService(provider), "test-model"),
        workspace,
        dataset,
        manifest,
        max_attempts=3,
    )
    assert report.passed == report.total == 24 and report.failed == 0
    assert provider.calls == 24
    assert {score.returned_model_id for score in report.cases} == {"test-revision"}
    assert len({score.request_id for score in report.cases}) == 24
    assert report.dataset_version == dataset.version and report.baseline_version == "demo-1"
    assert len(report.dataset_sha256) == 64
    assert report.prompt_version == runner.PROMPT_VERSION
    captured = capsys.readouterr().err
    assert len(captured.splitlines()) == 24
    assert cases[0].question not in captured
    assert all(c.actual_plan is not None for c in report.cases)
    assert '"actual_plan"' not in captured
    assert str(workspace) not in captured


@pytest.mark.integration
def test_preflight_rejects_changed_workspace_and_owner_role(query_data):
    database, owner, manifest, workspaces, _, _ = query_data
    with pytest.raises(ValueError, match="Restricted application role"):
        runner.preflight(owner, workspaces[0], manifest, [])
    with owner.session() as session:
        session.execute(
            update(FacilityRecord)
            .where(FacilityRecord.workspace_id == workspaces[0])
            .values(name="Edited baseline")
        )
    with pytest.raises(Exception, match="Workspace differs from baseline"):
        runner.preflight(database, workspaces[0], manifest, [])


@pytest.fixture
def cli(monkeypatch):
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url="postgresql+psycopg://space_corp_app:SECRET@localhost/example",
        default_workspace_id=uuid4(),
        llm_model_id="test-model",
        llm_api_key="SECRET",
        llm_reasoning_effort="medium",
    )
    monkeypatch.setattr(runner, "Settings", lambda: settings)
    database = Mock()
    monkeypatch.setattr(runner, "Database", Mock(return_value=database))
    preflight = Mock()
    monkeypatch.setattr(runner, "preflight", preflight)
    provider_calls = []

    @contextmanager
    def provider(settings):
        provider_calls.append(settings.llm_model_id)
        yield Mock()

    monkeypatch.setattr(runner, "configured_provider", provider)
    report = Mock(failed=0)
    report.model_dump_json.return_value = '{"passed":24,"failed":0}'
    evaluate = Mock(return_value=report)
    monkeypatch.setattr(runner, "evaluate", evaluate)
    return settings, database, preflight, provider_calls, evaluate, report


def test_cli_success_and_failure_exit_codes(cli, capsys):
    _, database, preflight, calls, evaluate, report = cli
    assert runner.main([]) == 0
    preflight.assert_called_once()
    assert calls == ["test-model"]
    assert evaluate.call_args.kwargs["max_attempts"] == 1
    assert evaluate.call_args.kwargs["reasoning_effort"] == "medium"
    database.dispose.assert_called_once()
    assert json.loads(capsys.readouterr().out)["passed"] == 24
    report.failed = 1
    assert runner.main(["--max-attempts", "2"]) == 1


def test_cli_preflight_failure_prevents_paid_calls(cli, capsys):
    _, database, preflight, calls, evaluate, _ = cli
    preflight.side_effect = RuntimeError("SECRET database password")
    assert runner.main([]) == 2
    assert calls == []
    evaluate.assert_not_called()
    database.dispose.assert_called_once()
    assert "SECRET" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "field,value",
    [
        ("environment", "production"),
        ("llm_api_key", None),
        ("database_url", None),
        ("default_workspace_id", None),
    ],
)
def test_cli_missing_or_production_settings_prevent_work(cli, field, value):
    settings, _, preflight, calls, _, _ = cli
    setattr(settings, field, value)
    assert runner.main([]) == 2
    preflight.assert_not_called()
    assert not calls


def test_cli_invalid_dataset_prevents_paid_calls(cli, tmp_path):
    bad = tmp_path / "invalid.json"
    bad.write_text("{}")
    assert runner.main(["--dataset", str(bad)]) == 2
    assert not cli[3]


def test_cli_setup_error_cleans_up_and_omits_exception(cli, capsys):
    cli[4].side_effect = RuntimeError("SECRET")
    assert runner.main([]) == 2
    cli[1].dispose.assert_called_once()
    assert "SECRET" not in capsys.readouterr().err


@pytest.mark.integration
def test_preflight_rejects_incorrect_oracle(query_data):
    database, _, manifest, workspaces, _, _ = query_data
    case = resolve_case(load_evaluation().cases[0], manifest, workspaces[0])
    wrong = case.model_copy(update={"expected_result": None})
    with pytest.raises(ValueError, match="Baseline evidence mismatch"):
        runner.preflight(database, workspaces[0], manifest, [wrong])


def test_telemetry_restores_handlers_on_failure():
    import logging

    loggers = [logging.getLogger(name) for name in ("app.llm.service", "app.queries.service")]
    before = [
        (logger.handlers[:], logger.level, logger.propagate, logger.disabled) for logger in loggers
    ]
    with pytest.raises(RuntimeError), runner.telemetry():
        raise RuntimeError("stop")
    assert [
        (logger.handlers, logger.level, logger.propagate, logger.disabled) for logger in loggers
    ] == before


def test_invalid_argument_limits_fail_before_setup(cli):
    with pytest.raises(SystemExit) as error:
        runner.main(["--max-attempts", "4"])
    assert error.value.code == 2
    cli[2].assert_not_called()
    assert not cli[3]


def test_safe_diagnostics_identify_wrong_decline_reason():
    case, workspace = fixture_case(-1)
    actual = outcome(case, workspace).model_copy(
        update={"plan": DeclinedPlan(operation="declined", reason="missing_input")}
    )
    score = runner.score_case(case, actual, 1)
    assert not score.passed
    assert score.actual_operation == "declined"
    assert score.actual_decline_reason == "missing_input"
    assert score.mismatched_plan_fields == ("reason",)


def test_local_plan_diagnostics_are_separate_from_content_free_event_fields():
    case, workspace = fixture_case()
    actual = outcome(case, workspace)
    plan = actual.plan.model_copy(update={"equipment_model_id": uuid4()})
    score = runner.score_case(case, actual.model_copy(update={"plan": plan}), 1)
    assert score.mismatched_plan_fields == ("equipment_model_id",)
    assert score.actual_operation == "facility_equipment"
    assert score.actual_decline_reason is None
    assert score.actual_plan == plan.model_dump(mode="json")
    assert str(plan.equipment_model_id) not in score.model_dump_json(exclude={"actual_plan"})
    assert str(workspace) not in score.model_dump_json()
    assert case.question not in score.model_dump_json()


@pytest.mark.parametrize("operator,value,passes", [("lte", 1, True), ("lte", 2, False)])
def test_integer_bound_equivalence_preserves_intent_without_hiding_off_by_one(
    operator, value, passes
):
    case, workspace = fixture_case(12)
    assert case.expected_plan.quantity.operator == "lt" and case.expected_plan.quantity.value == 2
    actual = outcome(case, workspace)
    quantity = actual.plan.quantity.model_copy(update={"operator": operator, "value": value})
    actual = actual.model_copy(
        update={"plan": actual.plan.model_copy(update={"quantity": quantity})}
    )
    assert runner.score_case(case, actual, 1).passed is passes


def test_inclusive_integer_lower_bound_matches_strict_predecessor():
    assert runner._canonical({"quantity": {"operator": "gte", "value": 1}}) == runner._canonical(
        {"quantity": {"operator": "gt", "value": 0}}
    )
    assert runner._canonical({"quantity": {"operator": "gte", "value": 1}}) != runner._canonical(
        {"quantity": {"operator": "gt", "value": 1}}
    )


@pytest.mark.parametrize(
    "operation,field,enum_name",
    [
        ("incidents", "statuses", "IncidentStatus"),
        ("incidents", "severities", "IncidentSeverity"),
        ("work_orders", "statuses", "WorkOrderStatus"),
        ("work_orders", "priorities", "WorkOrderPriority"),
        ("facility_equipment", "unit_statuses", "EquipmentOperationalStatus"),
    ],
)
def test_full_nonnullable_enum_selection_is_unrestricted_but_subset_is_not(
    operation, field, enum_name
):
    values = [item.value for item in getattr(runner, enum_name)]
    unrestricted = {"operation": operation, field: None}
    assert runner._canonical({"operation": operation, field: values}) == unrestricted
    assert runner._canonical({"operation": operation, field: values[:-1]}) != unrestricted


def test_full_incident_status_existence_filter_cannot_be_dropped():
    for operation in ("compatible_stock", "facility_equipment"):
        assert runner._canonical(
            {"operation": operation, "incident_statuses": list(runner.IncidentStatus)}
        ) != {
            "operation": operation,
            "incident_statuses": None,
        }


@pytest.mark.integration
@pytest.mark.parametrize(
    "operation,field,enum_name",
    [
        ("incidents", "statuses", "IncidentStatus"),
        ("incidents", "severities", "IncidentSeverity"),
        ("work_orders", "statuses", "WorkOrderStatus"),
        ("work_orders", "priorities", "WorkOrderPriority"),
        ("facility_equipment", "unit_statuses", "EquipmentOperationalStatus"),
    ],
)
def test_full_enum_equivalence_matches_database_semantics(query_data, operation, field, enum_name):
    from app.queries.contracts import QUERY_PLAN, QueryContext
    from app.queries.operations import OperationsQueryExecutor

    database, _, _, workspaces, _, _ = query_data
    context = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspaces[0])
    proposal = {"operation": operation}
    if operation == "work_orders":
        proposal["as_of"] = "2026-01-31T12:00:00Z"
    executor = (
        runner.EquipmentQueryExecutor(database)
        if operation == "facility_equipment"
        else OperationsQueryExecutor(database)
    )
    expected = executor.execute(context, QUERY_PLAN.validate_python(proposal)).result
    proposal[field] = [item.value for item in getattr(runner, enum_name)]
    assert executor.execute(context, QUERY_PLAN.validate_python(proposal)).result == expected


@pytest.mark.parametrize("expected_kind", ["supported", "declined"])
def test_synthetic_reviewer_never_approves_wrong_pending_intent(expected_kind):
    from app.queries.contracts import InventoryPlan

    dataset = load_evaluation()
    fixture = next(c for c in dataset.cases if c.kind == expected_kind)
    dataset = dataset.model_copy(update={"cases": (fixture,)})
    ctx = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=uuid4())
    pending = QueryOutcome(
        context=ctx,
        planning_operation_id=uuid4(),
        resolution_operation_id=uuid4(),
        plan=InventoryPlan(operation="inventory"),
        scope_status="awaiting_confirmation",
    )
    service = Mock(model_id="test-model")
    service.ask.return_value = pending
    report = runner.evaluate(service, ctx.workspace_id, dataset, load_manifest(), max_attempts=1)
    assert report.failed == 1
    assert not report.cases[0].intent_match
    assert report.cases[0].scope_status == "awaiting_confirmation"
    service.confirm_scope.assert_not_called()
