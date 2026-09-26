"""Evaluate the configured live planner against frozen questions and database evidence."""

import argparse
import hashlib
import json
import logging
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.config import Settings
from app.database import Database
from app.equipment.domain import EquipmentOperationalStatus
from app.llm.configuration import configured_provider
from app.llm.contracts import ReasoningEffort
from app.llm.service import ModelService
from app.operations.domain import (
    IncidentSeverity,
    IncidentStatus,
    WorkOrderPriority,
    WorkOrderStatus,
)
from app.queries.contracts import DeclinedPlan, Frozen, QueryContext, QueryPageRequest
from app.queries.equipment import EquipmentQueryExecutor
from app.queries.errors import QueryError
from app.queries.execution import pinned_query_session
from app.queries.operations import OperationsQueryExecutor
from app.queries.planning import PROMPT_ID, PROMPT_VERSION, planning_prompt
from app.queries.service import QueryOutcome, QueryService
from scripts.dataset_manifest import Manifest, digest, load_manifest, shared_id
from scripts.query_evaluation_dataset import (
    DEFAULT_EVALUATION,
    EvaluationDataset,
    ResolvedCase,
    evidence_matches,
    load_evaluation,
    resolve_case,
)
from scripts.seed_dataset import validate_workspace


class CaseScore(Frozen):
    key: str
    request_id: UUID
    operation_id: UUID
    planning_operation_id: UUID | None = None
    returned_model_id: str | None = None
    actual_plan: dict[str, Any] | None = None
    scope_status: str = "not_required"
    actual_operation: str | None = None
    actual_decline_reason: str | None = None
    mismatched_plan_fields: tuple[str, ...] = ()
    intent_match: bool = False
    evidence_match: bool = False
    execution_policy_match: bool = False
    passed: bool = False
    error_kind: str | None = None
    failure_category: str | None = None
    duration_ms: float


class EvaluationReport(Frozen):
    report_version: str = "3"
    execution_mode: str = "legacy_automatic"
    reasoning_effort: ReasoningEffort | None = None
    dataset_purpose: str
    implementation_sha256: str
    prompt_sha256: str
    run_id: UUID
    started_at: datetime
    dataset_version: str
    dataset_sha256: str
    baseline_version: str
    baseline_sha256: str
    catalog_version: str
    model_id: str
    prompt_id: str = PROMPT_ID
    prompt_version: str = PROMPT_VERSION
    max_attempts: int
    cases: tuple[CaseScore, ...]
    total: int
    passed: int
    failed: int


def _canonical(value: Any) -> Any:
    """Normalize set ordering and equivalent integer bounds, not intent differences."""
    if isinstance(value, dict):
        if set(value) == {"operator", "value"} and type(value["value"]) is int:
            if value["operator"] == "lte":
                return {"operator": "lt", "value": value["value"] + 1}
            if value["operator"] == "gte":
                return {"operator": "gt", "value": value["value"] - 1}
        # Only non-null attributes of already-selected rows: existence predicates are different.
        domain_enums: dict[str, dict[str, type[StrEnum]]] = {
            "incidents": {"statuses": IncidentStatus, "severities": IncidentSeverity},
            "work_orders": {"statuses": WorkOrderStatus, "priorities": WorkOrderPriority},
            "facility_equipment": {"unit_statuses": EquipmentOperationalStatus},
        }
        selection_enums = domain_enums.get(value.get("operation", ""), {})
        return {
            key: None
            if key in selection_enums
            and isinstance(item, list)
            and set(item) == {member.value for member in selection_enums[key]}
            else _canonical(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return sorted(value)
    return value


def implementation_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "app/queries").glob("*.py")) + sorted((root / "app/llm").glob("*.py"))
    paths += [
        root / "app/database.py",
        root / "scripts/evaluate_queries.py",
        root / "scripts/query_evaluation_dataset.py",
    ]
    return digest(
        {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    )


def prompt_digest() -> str:
    # Fixed sentinels exclude per-request text/time while fingerprinting instructions/schema.
    return digest(planning_prompt("", datetime(2000, 1, 1, tzinfo=UTC)))


def score_case(expected: ResolvedCase, actual: QueryOutcome, duration_ms: float) -> CaseScore:
    actual_plan = _canonical(actual.plan.model_dump(mode="json"))
    expected_plan = _canonical(expected.expected_plan.model_dump(mode="json"))
    mismatched_fields = tuple(
        key
        for key in sorted(actual_plan.keys() | expected_plan.keys())
        if (key in actual_plan) != (key in expected_plan)
        or actual_plan.get(key) != expected_plan.get(key)
    )
    intent = not mismatched_fields
    evidence = evidence_matches(
        actual.response.result if actual.response is not None else None, expected.expected_result
    )
    policy = (actual.response is not None) == expected.execution_allowed
    if not expected.execution_allowed and actual.response is not None:
        category = "unexpected_execution"
    elif expected.execution_allowed and isinstance(actual.plan, DeclinedPlan):
        category = "unnecessary_decline"
    elif not intent:
        category = "wrong_query" if expected.execution_allowed else "decline_category"
    elif not evidence or not policy:
        category = "wrong_evidence"
    else:
        category = None
    return CaseScore(
        failure_category=category,
        key=expected.key,
        request_id=actual.context.request_id,
        operation_id=actual.context.operation_id,
        planning_operation_id=actual.planning_operation_id,
        returned_model_id=actual.returned_model_id,
        actual_plan=actual.plan.model_dump(mode="json"),
        scope_status=actual.scope_status,
        actual_operation=actual.plan.operation,
        actual_decline_reason=actual.plan.reason if isinstance(actual.plan, DeclinedPlan) else None,
        mismatched_plan_fields=mismatched_fields,
        intent_match=intent,
        evidence_match=evidence,
        execution_policy_match=policy,
        passed=intent and evidence and policy,
        duration_ms=duration_ms,
    )


def preflight(
    database: Database, workspace: UUID, manifest: Manifest, cases: Sequence[ResolvedCase]
) -> None:
    """Check the restricted role, exact baseline rows, pin and oracle before paid calls."""
    context = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace)
    with pinned_query_session(database, context) as (session, release):
        role = session.execute(
            text(
                "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
        if role[0] != "space_corp_app" or role[1] or role[2]:
            raise ValueError("Restricted application role required")
        if release != shared_id(manifest.catalog.version, "release", manifest.catalog.version):
            raise ValueError("Catalog pin mismatch")
        validate_workspace(session, workspace, manifest)
    equipment, operations = EquipmentQueryExecutor(database), OperationsQueryExecutor(database)
    for case in cases:
        if isinstance(case.expected_plan, DeclinedPlan):
            continue
        executor = (
            equipment
            if case.expected_plan.operation in ("facility_equipment", "compatible_stock")
            else operations
        )
        actual = executor.execute(context, case.expected_plan, QueryPageRequest(limit=100))
        if not evidence_matches(actual.result, case.expected_result):
            raise ValueError("Baseline evidence mismatch")


def evaluate(
    service: QueryService,
    workspace: UUID,
    dataset: EvaluationDataset,
    manifest: Manifest,
    *,
    max_attempts: int,
    reasoning_effort: ReasoningEffort | None = None,
) -> EvaluationReport:
    """Plan first; simulate exact-plan review locally, never teaching the model expected intent."""
    started = datetime.now(UTC)
    scores = []
    for fixture in dataset.cases:
        case = resolve_case(fixture, manifest, workspace)
        context = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace)
        tick = time.monotonic()
        try:
            outcome = service.ask(context, case.question, QueryPageRequest(limit=100))
            # Synthetic reviewer simulation, AFTER planning: never send expectations to the model.
            # Approve only a supported plan whose full intent matches the independent oracle.
            if (
                outcome.scope_status == "awaiting_confirmation"
                and case.execution_allowed
                and not isinstance(outcome.plan, DeclinedPlan)
                and _canonical(outcome.plan.model_dump(mode="json"))
                == _canonical(case.expected_plan.model_dump(mode="json"))
            ):
                outcome = service.confirm_scope(context, outcome, outcome.plan)
            score = score_case(case, outcome, (time.monotonic() - tick) * 1000)
        except Exception as error:
            score = CaseScore(
                key=case.key,
                request_id=context.request_id,
                operation_id=context.operation_id,
                error_kind=error.kind.value if isinstance(error, QueryError) else "internal_error",
                failure_category="execution_error",
                duration_ms=(time.monotonic() - tick) * 1000,
            )
        scores.append(score)
        print(
            json.dumps(
                {
                    "event": "evaluation_case",
                    **score.model_dump(mode="json", exclude={"actual_plan"}),
                }
            ),
            file=sys.stderr,
            flush=True,
        )
    passed = sum(score.passed for score in scores)
    return EvaluationReport(
        execution_mode="scope_confirmation",
        reasoning_effort=reasoning_effort,
        run_id=uuid4(),
        started_at=started,
        dataset_version=dataset.version,
        dataset_purpose=dataset.purpose,
        prompt_sha256=prompt_digest(),
        implementation_sha256=implementation_digest(),
        dataset_sha256=digest(dataset.model_dump(mode="json")),
        baseline_version=manifest.version,
        baseline_sha256=dataset.baseline_sha256,
        catalog_version=manifest.catalog.version,
        model_id=service.model_id,
        max_attempts=max_attempts,
        cases=tuple(scores),
        total=len(scores),
        passed=passed,
        failed=len(scores) - passed,
    )


@contextmanager
def telemetry() -> Iterator[None]:
    """Only content-free application traces; restore caller logging on every exit."""
    saved = []
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    for name in ("app.llm.service", "app.queries.service"):
        logger = logging.getLogger(name)
        saved.append((logger, logger.handlers[:], logger.level, logger.propagate, logger.disabled))
        logger.handlers, logger.propagate, logger.disabled = [handler], False, False
        logger.setLevel(logging.INFO)
    try:
        yield
    finally:
        for logger, handlers, level, propagate, disabled in saved:
            logger.handlers, logger.propagate, logger.disabled = handlers, propagate, disabled
            logger.setLevel(level)
        handler.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=UUID, help="Defaults to configured development workspace."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--max-attempts", type=int, choices=(1, 2, 3), default=1)
    options = parser.parse_args(argv)
    database = None
    try:
        settings = Settings()
        workspace = options.workspace or settings.default_workspace_id
        if (
            settings.environment == "production"
            or settings.database_url is None
            or workspace is None
            or not settings.llm_model_id
            or settings.llm_api_key is None
            or not settings.llm_api_key.get_secret_value().strip()
        ):
            raise ValueError("Missing evaluation configuration")
        manifest = load_manifest()
        dataset = load_evaluation(options.dataset, manifest=manifest)
        cases = [resolve_case(case, manifest, workspace) for case in dataset.cases]
        database = Database(str(settings.database_url))
        preflight(database, workspace, manifest, cases)
    except Exception:
        if database is not None:
            database.dispose()
        print(
            "Evaluation preflight failed. Check settings, dataset, migrations, application role, and seeded workspace.",
            file=sys.stderr,
        )
        return 2
    try:
        with telemetry(), configured_provider(settings) as provider:
            report = evaluate(
                QueryService(
                    database,
                    ModelService(provider, max_attempts=options.max_attempts),
                    settings.llm_model_id,
                ),
                workspace,
                dataset,
                manifest,
                max_attempts=options.max_attempts,
                reasoning_effort=settings.llm_reasoning_effort,
            )
        print(report.model_dump_json(indent=2))
        return 0 if report.failed == 0 else 1
    except Exception:
        print("Evaluation setup failed; no complete report is available.", file=sys.stderr)
        return 2
    finally:
        database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
