"""Assess a predeclared batch of saved reports offline; never calls a model."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.dataset_manifest import digest
from scripts.evaluate_queries import EvaluationReport, implementation_digest, prompt_digest
from scripts.query_evaluation_dataset import load_evaluation

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "data/evaluations/query-protocol-1.json"


def assess(paths: list[Path], protocol_path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol["prompt_sha256"] != prompt_digest()
        or protocol["implementation_sha256"] != implementation_digest()
    ):
        raise ValueError("Frozen implementation changed; define a new assessment protocol")
    reports = [EvaluationReport.model_validate_json(path.read_text()) for path in paths]
    groups = protocol["datasets"]
    repeats = protocol["repetitions"]
    if len(reports) != len(groups) * repeats or len({r.run_id for r in reports}) != len(reports):
        raise ValueError("Exactly the predeclared unique runs are required")
    if len({c.request_id for r in reports for c in r.cases}) != sum(len(r.cases) for r in reports):
        raise ValueError("Repeated case request IDs")
    if any(r.dataset_version not in groups for r in reports):
        raise ValueError("Unexpected dataset")
    returned_models = {c.returned_model_id for r in reports for c in r.cases if c.returned_model_id}
    if len(returned_models) != 1:
        raise ValueError("Missing or mixed returned model identities")
    summaries = {}
    for version, spec in groups.items():
        dataset = load_evaluation(ROOT / spec["path"])
        if digest(dataset.model_dump(mode="json")) != spec["sha256"]:
            raise ValueError("Frozen dataset changed")
        runs = [r for r in reports if r.dataset_version == version]
        if len(runs) != repeats:
            raise ValueError("Wrong number of runs per dataset")
        case_keys = {c.key for c in dataset.cases}
        for run in runs:
            if (
                run.report_version != "3"
                or run.implementation_sha256 != protocol["implementation_sha256"]
                or run.model_id != protocol["model_id"]
                or run.prompt_sha256 != protocol["prompt_sha256"]
                or run.prompt_version != protocol["prompt_version"]
                or run.prompt_id != "bounded-query"
                or run.max_attempts != 1
                or run.dataset_sha256 != spec["sha256"]
                or run.dataset_purpose != dataset.purpose
                or run.baseline_sha256 != dataset.baseline_sha256
                or run.baseline_version != dataset.baseline_version
                or run.catalog_version != dataset.catalog_version
                or len(run.cases) != len(case_keys)
                or {c.key for c in run.cases} != case_keys
                or run.total != len(run.cases)
                or run.passed != sum(c.passed for c in run.cases)
                or run.failed != run.total - run.passed
                or any(
                    c.passed != (c.intent_match and c.evidence_match and c.execution_policy_match)
                    for c in run.cases
                )
                or any(c.passed and not c.returned_model_id for c in run.cases)
            ):
                raise ValueError("Incomplete or incompatible report")
        scores = [c for r in runs for c in r.cases]
        failures = Counter(c.failure_category or "unclassified" for c in scores if not c.passed)
        supported_keys = {c.key for c in dataset.cases if c.kind == "supported"}
        supported = [c for c in scores if c.key in supported_keys]
        declined = [c for c in scores if c.key not in supported_keys]
        supported_rate = sum(c.passed for c in supported) / len(supported)
        decline_rate = sum(c.passed for c in declined) / len(declined)
        hard_failures = sum(
            n
            for kind, n in failures.items()
            if kind not in ("unnecessary_decline", "decline_category")
        )
        summaries[version] = {
            "runs": len(runs),
            "observations": len(scores),
            "supported_pass_rate": supported_rate,
            "decline_pass_rate": decline_rate,
            "failure_categories": dict(failures),
            "per_case_passes": {
                key: sum(c.passed for c in scores if c.key == key) for key in sorted(case_keys)
            },
            "meets_quality_target": hard_failures == 0
            and supported_rate >= protocol["minimum_supported_pass_rate"]
            and decline_rate >= protocol["minimum_decline_pass_rate"],
        }
    return {
        "protocol_version": protocol["version"],
        "run_ids": [str(r.run_id) for r in reports],
        "returned_model_id": next(iter(returned_models)),
        "datasets": summaries,
        "meets_quality_target": all(s["meets_quality_target"] for s in summaries.values()),
        "scope": "Small synthetic pilot assessment, not a production reliability guarantee",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    options = parser.parse_args()
    try:
        result = assess(options.reports, options.protocol)
    except Exception:
        print(
            "Assessment rejected: require complete unique reports matching the frozen protocol and implementation.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["meets_quality_target"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
