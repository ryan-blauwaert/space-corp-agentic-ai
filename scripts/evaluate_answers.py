"""Record fixed-evidence or opt-in live answers for independent factual review."""

import argparse
import hashlib
import json
import logging
import re
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from app.answers.contracts import AnswerRequest, AnswerResponse, AnswerTurn
from app.answers.rendering import render_answer
from app.answers.service import RENDERER_VERSION, AnswerService
from app.answers.validation import evidence_references
from app.config import Settings
from app.database import Database
from app.llm.configuration import configured_provider
from app.llm.service import ModelService
from app.queries.contracts import (
    DeclinedPlan,
    Frozen,
    QueryContext,
    QueryPageRequest,
    QueryResponse,
)
from app.queries.errors import QueryError
from app.queries.service import QueryOutcome, QueryService, needs_scope_confirmation
from scripts.answer_evaluation_dataset import (
    DEFAULT_ANSWERS,
    AnswerEvaluationDataset,
    load_answer_evaluation,
)
from scripts.dataset_manifest import Manifest, digest, load_manifest, shared_id
from scripts.evaluate_queries import (
    _canonical,
    implementation_digest,
    preflight,
    prompt_digest,
    score_case,
)
from scripts.query_evaluation_dataset import (
    DEFAULT_EVALUATION,
    EvaluationDataset,
    ResolvedCase,
    load_evaluation,
    resolve_case,
)

ROOT = Path(__file__).resolve().parents[1]
UUID_TEXT = re.compile(
    r"(?<![0-9a-f])(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})(?![0-9a-f])",
    re.I,
)


class AnswerCaseReport(Frozen):
    key: str
    turn: AnswerTurn | None = None
    error_kind: str | None = None
    events: tuple[dict[str, Any], ...] = ()
    checks: dict[str, bool]


class AnswerEvaluationReport(Frozen):
    version: Literal["1"] = "1"
    run_id: UUID
    started_at: datetime
    mode: Literal["fixed_evidence", "live_scope_confirmation"]
    workspace_id: UUID
    query_version: str
    query_sha256: str
    answer_version: str
    answer_sha256: str
    implementation_sha256: str
    prompt_sha256: str
    renderer_version: str
    model_id: str | None
    reasoning_effort: str | None
    max_attempts: int
    cases: tuple[AnswerCaseReport, ...]
    review_status: Literal["not_measured", "required"] = "not_measured"


def answer_digest() -> str:
    paths = sorted((ROOT / "app/answers").glob("*.py")) + [
        ROOT / "app/config.py",
        ROOT / "scripts/evaluate_answers.py",
        ROOT / "scripts/assess_answers.py",
        ROOT / "scripts/answer_evaluation_dataset.py",
    ]
    return digest(
        {
            "query_implementation": implementation_digest(),
            "answer_files": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
            },
        }
    )


@contextmanager
def capture_events() -> Iterator[list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []

    class Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            events.append(json.loads(record.getMessage()))

    handler = Handler()
    saved = []
    for name in ("app.llm.service", "app.queries.service", "app.answers.service"):
        logger = logging.getLogger(name)
        saved.append((logger, logger.handlers[:], logger.level, logger.propagate, logger.disabled))
        logger.handlers, logger.propagate, logger.disabled = [handler], False, False
        logger.setLevel(logging.INFO)
    try:
        yield events
    finally:
        for logger, handlers, level, propagate, disabled in saved:
            logger.handlers, logger.propagate, logger.disabled = handlers, propagate, disabled
            logger.setLevel(level)
        handler.close()


def fixed_turn(case: ResolvedCase, workspace: UUID, manifest: Manifest) -> AnswerTurn:
    ctx = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace)
    plan = case.expected_plan
    query = QueryOutcome(
        context=ctx,
        planning_operation_id=uuid4(),
        resolution_operation_id=uuid4(),
        plan=plan,
        scope_status="confirmed"
        if not isinstance(plan, DeclinedPlan) and needs_scope_confirmation(plan)
        else "not_required",
        page_request=QueryPageRequest(limit=100),
        response=QueryResponse(
            context=ctx,
            catalog_release_id=shared_id(
                manifest.catalog.version, "release", manifest.catalog.version
            ),
            result=case.expected_result,
        )
        if case.expected_result
        else None,
    )
    request = AnswerRequest(question=case.question, query=query)
    return AnswerTurn(
        request=request,
        response=AnswerResponse(
            context=ctx, synthesis_operation_id=uuid4(), outcome=render_answer(request)
        ),
    )


def automatic_checks(
    case: ResolvedCase, turn: AnswerTurn | None, events: Sequence[dict[str, Any]], *, live: bool
) -> dict[str, bool]:
    if turn is None:
        return {k: False for k in ("query", "state", "references", "coverage", "trace")}
    score = score_case(case, turn.request.query, 0)
    outcome = turn.response.outcome
    expected_state = (
        "declined"
        if not case.execution_allowed
        else "no_results"
        if case.expected_result and case.expected_result.page.total == 0
        else "answered"
    )
    state = (
        (outcome.status == "answered")
        if expected_state == "answered"
        else (outcome.status == "cautious" and outcome.reason == expected_state)
    )
    references = True
    coverage = True
    if outcome.status == "answered":
        allowed = evidence_references(case.expected_result) if case.expected_result else frozenset()
        supplied = set(outcome.answer.references)
        mentioned = {UUID(m[0]) for m in UUID_TEXT.finditer(outcome.answer.text)}
        references = supplied == allowed and mentioned <= {r.record_id for r in supplied}
        page = turn.request.query.response.result.page if turn.request.query.response else None
        coverage = page is not None and outcome.coverage == (
            "complete" if page.offset == 0 and len(page.rows) == page.total else "partial"
        )
    trace = True
    if live:
        ctx = turn.response.context
        linked = [
            e
            for e in events
            if e.get("request_id") == str(ctx.request_id)
            and e.get("query_operation_id") == str(ctx.operation_id)
        ]
        answer_events = [
            e for e in linked if e.get("operation_id") == str(turn.response.synthesis_operation_id)
        ]
        trace = all(
            any(e.get("event") == name for e in answer_events)
            for name in ("answer_operation", "answer_render")
        )
        trace = trace and all(
            any(
                e.get("event") == name and e.get("operation_id") == str(operation_id)
                for e in linked
            )
            for name, operation_id in (
                ("query_planning", turn.request.query.planning_operation_id),
                ("query_resolution", turn.request.query.resolution_operation_id),
            )
        )
        trace = trace and (
            any(e.get("event") == "query_execution" for e in linked)
            == (turn.request.query.response is not None)
        )
        attempts = [e for e in events if e.get("event") == "model_attempt"]
        trace = (
            trace
            and len(attempts) == 1
            and attempts[0].get("request_id") == str(ctx.request_id)
            and attempts[0].get("attempt_count") == 1
        )
    return {
        "query": score.passed and turn.request.question == case.question,
        "state": state,
        "references": references,
        "coverage": coverage,
        "trace": trace,
    }


def evaluate_answers(
    queries: EvaluationDataset,
    answers: AnswerEvaluationDataset,
    manifest: Manifest,
    workspace: UUID,
    service: AnswerService | None = None,
    *,
    model_id: str | None = None,
    reasoning_effort: str | None = None,
    progress_folder: Path | None = None,
) -> AnswerEvaluationReport:
    rows = []
    run_id, started_at = uuid4(), datetime.now(UTC)
    if progress_folder is not None:
        with (progress_folder / "run.json").open("x") as output:
            json.dump(
                {
                    "run_id": str(run_id),
                    "started_at": started_at.isoformat(),
                    "planned_cases": [c.key for c in queries.cases],
                    "mode": "live_scope_confirmation" if service else "fixed_evidence",
                    "model_id": model_id,
                    "reasoning_effort": reasoning_effort,
                    "implementation_sha256": answer_digest(),
                },
                output,
                indent=2,
            )
        (progress_folder / "cases.jsonl").touch(exist_ok=False)
    for fixture in queries.cases:
        case = resolve_case(fixture, manifest, workspace)
        turn = None
        error_kind = None
        with capture_events() as events:
            try:
                if service is None:
                    turn = fixed_turn(case, workspace, manifest)
                else:
                    ctx = QueryContext(
                        request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace
                    )
                    turn = service.ask(ctx, case.question, QueryPageRequest(limit=100))
                    proposal = turn.request.query
                    if (
                        proposal.scope_status == "awaiting_confirmation"
                        and case.execution_allowed
                        and not isinstance(proposal.plan, DeclinedPlan)
                        and _canonical(proposal.plan.model_dump(mode="json"))
                        == _canonical(case.expected_plan.model_dump(mode="json"))
                    ):
                        # Review simulation after planning; no expected facts enter the prompt.
                        turn = service.confirm_scope(ctx, turn, proposal.plan)
            except Exception as error:
                error_kind = error.kind.value if isinstance(error, QueryError) else "internal_error"
        rows.append(
            AnswerCaseReport(
                key=case.key,
                turn=turn,
                error_kind=error_kind,
                events=tuple(events),
                checks=automatic_checks(case, turn, events, live=service is not None),
            )
        )
        if progress_folder is not None:
            with (progress_folder / "cases.jsonl").open("a") as output:
                output.write(rows[-1].model_dump_json() + "\n")
    return AnswerEvaluationReport(
        run_id=run_id,
        started_at=started_at,
        mode="live_scope_confirmation" if service else "fixed_evidence",
        workspace_id=workspace,
        query_version=queries.version,
        query_sha256=digest(queries.model_dump(mode="json")),
        answer_version=answers.version,
        answer_sha256=digest(answers.model_dump(mode="json")),
        implementation_sha256=answer_digest(),
        prompt_sha256=prompt_digest(),
        renderer_version=RENDERER_VERSION,
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        max_attempts=1 if service else 0,
        cases=tuple(rows),
    )


def write_report(
    folder: Path, report: AnswerEvaluationReport, answers: AnswerEvaluationDataset
) -> None:
    # Caller creates the exclusive directory before any paid calls.
    (folder / "report.json").write_text(report.model_dump_json(indent=2) + "\n")
    expectations = {c.query_case: c for c in answers.cases}
    review: dict[str, Any] = {
        "report_sha256": digest(report.model_dump(mode="json")),
        "reviewer": None,
        "review_kind": "evidence_inspection",
        "cases": [],
    }
    lines = [
        "# Answer review",
        "",
        "Review against the question, expected evidence, and required facts. Do not mark unreviewed claims as passing.",
    ]
    manifest = load_manifest()
    dataset = load_evaluation(ROOT / f"data/evaluations/{report.query_version}.json")
    fixtures = {c.key: c for c in dataset.cases}
    for c in report.cases:
        expectation = expectations[c.key]
        expected = resolve_case(fixtures[c.key], manifest, report.workspace_id)
        review["cases"].append(
            {
                "key": c.key,
                "required_facts_covered": [None] * len(expectation.required_facts),
                "supported_claim_count": None,
                "unsupported_claims": None,
                "cautious_and_scope_correct": None,
                "notes": "",
            }
        )
        delivered = (
            c.turn.response.outcome.model_dump(mode="json")
            if c.turn
            else {"error_kind": c.error_kind}
        )
        lines += [
            "",
            "## " + c.key,
            "",
            expected.question,
            "",
            "Required facts:",
            *["- " + f for f in expectation.required_facts],
            "",
            "Prohibited claims:",
            *["- " + f for f in expectation.prohibited_claims],
            "",
            "Expected evidence:",
            "```json",
            json.dumps(
                expected.expected_result.model_dump(mode="json")
                if expected.expected_result
                else None,
                indent=2,
            ),
            "```",
            "",
            "Delivered outcome:",
            "```json",
            json.dumps(delivered, indent=2),
            "```",
        ]
    (folder / "review.json").write_text(json.dumps(review, indent=2) + "\n")
    (folder / "review.md").write_text("\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Sends questions/schema to the configured model; requires explicit approval.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(argv)
    database = None
    try:
        queries = load_evaluation(options.dataset)
        answers = load_answer_evaluation(options.answers, query_path=options.dataset)
        manifest = load_manifest()
        options.output.mkdir(parents=True, exist_ok=False)
        if options.live:
            settings = Settings()
            workspace = settings.default_workspace_id
            if (
                settings.environment == "production"
                or not settings.database_url
                or not workspace
                or not settings.llm_model_id
            ):
                raise ValueError("Missing development configuration")
            database = Database(str(settings.database_url))
            preflight(
                database,
                workspace,
                manifest,
                [resolve_case(c, manifest, workspace) for c in queries.cases],
            )
            with configured_provider(settings) as provider:
                service = AnswerService(
                    QueryService(
                        database, ModelService(provider, max_attempts=1), settings.llm_model_id
                    )
                )
                report = evaluate_answers(
                    queries,
                    answers,
                    manifest,
                    workspace,
                    service,
                    model_id=settings.llm_model_id,
                    reasoning_effort=settings.llm_reasoning_effort,
                    progress_folder=options.output,
                )
        else:
            report = evaluate_answers(
                queries, answers, manifest, UUID(int=1), progress_folder=options.output
            )
        write_report(options.output, report, answers)
        failures = sum(c.error_kind is not None or not all(c.checks.values()) for c in report.cases)
        print(
            json.dumps(
                {
                    "cases": len(report.cases),
                    "automatic_failures": failures,
                    "factual_assessment": "not_measured",
                    "output": str(options.output),
                }
            )
        )
        return 1 if failures else 0
    except Exception:
        print(
            "Answer evaluation failed or output directory exists; preserve any partial run. Check configuration and fixtures.",
            file=sys.stderr,
        )
        return 2
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
