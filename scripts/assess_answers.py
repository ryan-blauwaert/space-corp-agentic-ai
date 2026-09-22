"""Assess complete answer reports and independent human reviews offline."""

import argparse
import json
import sys
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, StrictBool, model_validator

from app.queries.contracts import Frozen
from scripts.answer_evaluation_dataset import load_answer_evaluation
from scripts.dataset_manifest import digest, load_manifest
from scripts.evaluate_answers import ROOT, AnswerEvaluationReport, answer_digest, automatic_checks
from scripts.query_evaluation_dataset import load_evaluation, resolve_case


class CaseReview(Frozen):
    key: str
    required_facts_covered: tuple[StrictBool, ...]
    supported_claim_count: Annotated[int, Field(strict=True, ge=0)]
    unsupported_claims: tuple[str, ...]
    cautious_and_scope_correct: StrictBool
    notes: str


class AnswerReview(Frozen):
    report_sha256: str
    reviewer: str = Field(min_length=1, pattern=r"\S")
    review_kind: Literal["human"]
    cases: tuple[CaseReview, ...]

    @model_validator(mode="after")
    def unique_cases(self) -> "AnswerReview":
        if len({c.key for c in self.cases}) != len(self.cases):
            raise ValueError("Duplicate review case")
        return self


def assess_answer_report(report_path: Path, review_path: Path) -> dict[str, Any]:
    report = AnswerEvaluationReport.model_validate_json(report_path.read_text())
    review = AnswerReview.model_validate_json(review_path.read_text())
    if review.report_sha256 != digest(report.model_dump(mode="json")):
        raise ValueError("Review does not match report")
    if report.implementation_sha256 != answer_digest():
        raise ValueError("Implementation changed since report")
    queries = load_evaluation(ROOT / f"data/evaluations/{report.query_version}.json")
    answers = load_answer_evaluation(
        ROOT / f"data/evaluations/{report.answer_version}.json",
        query_path=ROOT / f"data/evaluations/{report.query_version}.json",
    )
    if report.query_sha256 != digest(
        queries.model_dump(mode="json")
    ) or report.answer_sha256 != digest(answers.model_dump(mode="json")):
        raise ValueError("Fixture drift")
    keys = {c.key for c in queries.cases}
    if (
        len(report.cases) != len(keys)
        or {c.key for c in report.cases} != keys
        or {c.key for c in review.cases} != keys
    ):
        raise ValueError("Incomplete report/review")
    expected_answers = {c.query_case: c for c in answers.cases}
    expected_queries = {c.key: c for c in queries.cases}
    reviewed = {c.key: c for c in review.cases}
    result = []
    manifest = load_manifest()
    for case in report.cases:
        expected = expected_answers[case.key]
        human = reviewed[case.key]
        if len(human.required_facts_covered) != len(expected.required_facts):
            raise ValueError("Every required fact needs a review")
        # Recompute mechanical checks; edited check booleans cannot make a report pass.
        resolved = resolve_case(expected_queries[case.key], manifest, report.workspace_id)
        checks = automatic_checks(
            resolved, case.turn, case.events, live=report.mode == "live_scope_confirmation"
        )
        if checks != case.checks:
            raise ValueError("Inconsistent automatic checks")
        has_answer = case.turn is not None and case.turn.response.outcome.status == "answered"
        if has_answer and human.supported_claim_count == 0 and not human.unsupported_claims:
            raise ValueError("Delivered answer cannot have zero reviewed factual claims")
        passed = (
            case.error_kind is None
            and all(checks.values())
            and all(human.required_facts_covered)
            and not human.unsupported_claims
            and human.cautious_and_scope_correct
        )
        result.append(
            {
                "key": case.key,
                "answerable": expected.outcome == "answered",
                "passed": passed,
                "automatic_checks": checks,
                "supported_claims": human.supported_claim_count,
                "unsupported_claims": len(human.unsupported_claims),
                "required_facts_covered": sum(human.required_facts_covered),
                "required_facts": len(human.required_facts_covered),
                "cautious_and_scope_correct": human.cautious_and_scope_correct,
            }
        )
    return {
        "run_id": str(report.run_id),
        "mode": report.mode,
        "query_version": report.query_version,
        "reviewer": review.reviewer,
        "cases": result,
        "all_cases_passed": all(c["passed"] for c in result),
        "scope": "Reviewed pilot report; batch acceptance is separate",
    }


def assess_batch(protocol_path: Path, folders: list[Path]) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text())
    if protocol["implementation_sha256"] != answer_digest():
        raise ValueError("Frozen implementation changed")
    specs = protocol["datasets"]
    if len(folders) != len(specs) * protocol["repetitions"]:
        raise ValueError("All planned runs required")
    reports = [
        AnswerEvaluationReport.model_validate_json((f / "report.json").read_text()) for f in folders
    ]
    if len({r.run_id for r in reports}) != len(reports):
        raise ValueError("Duplicate runs")
    returned = {
        c.turn.request.query.returned_model_id
        for r in reports
        for c in r.cases
        if c.turn and c.turn.request.query.returned_model_id
    }
    if len(returned) != 1:
        raise ValueError("Missing or mixed returned model IDs")
    request_ids = [c.turn.response.context.request_id for r in reports for c in r.cases if c.turn]
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("Repeated requests")
    for r in reports:
        spec = specs.get(r.query_version)
        if (
            not spec
            or r.mode != "live_scope_confirmation"
            or r.model_id != protocol["model_id"]
            or r.reasoning_effort != protocol["reasoning_effort"]
            or r.max_attempts != 1
            or r.prompt_sha256 != protocol["prompt_sha256"]
            or r.renderer_version != protocol["renderer_version"]
            or r.query_sha256 != spec["query_sha256"]
            or r.answer_sha256 != spec["answer_sha256"]
            or r.answer_version != spec["answer_version"]
        ):
            raise ValueError("Incompatible assessment report")
    assessed = [assess_answer_report(f / "report.json", f / "review.json") for f in folders]
    groups = {}
    for version in specs:
        matching = [a for a in assessed if a["query_version"] == version]
        if len(matching) != protocol["repetitions"]:
            raise ValueError("Wrong repetitions")
        cases = [c for a in matching for c in a["cases"]]
        supported = [c for c in cases if c["answerable"]]
        cautious = [c for c in cases if not c["answerable"]]
        supported_rate = sum(c["passed"] for c in supported) / len(supported)
        cautious_rate = sum(c["passed"] for c in cautious) / len(cautious)
        critical = any(
            c["unsupported_claims"]
            or not c["cautious_and_scope_correct"]
            or not all(c["automatic_checks"][k] for k in ("references", "coverage", "trace"))
            for c in cases
        )
        # Wrong queries/evidence and call errors remain critical, even if the rendered prose is plausible.
        for r in reports:
            if r.query_version == version:
                for c in r.cases:
                    if c.error_kind or (
                        not c.checks["query"]
                        and c.turn
                        and c.turn.request.query.plan.operation != "declined"
                    ):
                        critical = True
        repeat_pass = all(
            any(c["passed"] for c in supported if c["key"] == key)
            for key in {c["key"] for c in supported}
        )
        passed = (
            not critical
            and supported_rate >= protocol["minimum_answerable_pass_rate"]
            and cautious_rate == 1
            and repeat_pass
        )
        groups[version] = {
            "observations": len(cases),
            "answerable_pass_rate": supported_rate,
            "cautious_pass_rate": cautious_rate,
            "unsupported_claims": sum(c["unsupported_claims"] for c in cases),
            "meets_quality_target": passed,
        }
    return {
        "protocol": protocol["version"],
        "datasets": groups,
        "meets_quality_target": all(g["meets_quality_target"] for g in groups.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args()
    try:
        if args.protocol:
            result = assess_batch(args.protocol, args.folders)
            passed = result["meets_quality_target"]
        else:
            if len(args.folders) != 1:
                raise ValueError("Single reviewed report or frozen batch required")
            result = assess_answer_report(
                args.folders[0] / "report.json", args.folders[0] / "review.json"
            )
            passed = result["all_cases_passed"]
    except Exception:
        print(
            "Assessment incomplete or incompatible: require all matching reports and completed human reviews.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
