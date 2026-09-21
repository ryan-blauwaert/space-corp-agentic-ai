import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from scripts.answer_evaluation_dataset import DEFAULT_ANSWERS, load_answer_evaluation
from scripts.dataset_manifest import load_manifest
from scripts.query_evaluation_dataset import load_evaluation, resolve_case


def test_expectations_cover_every_canonical_and_additional_query():
    answers = load_answer_evaluation()
    queries = load_evaluation()
    assert len(answers.cases) == 24
    assert len(answers.challenges) == 8
    baseline = load_manifest()
    by_key = {c.query_case: c for c in answers.cases}
    domains = set()
    for case in queries.cases:
        resolved = resolve_case(case, baseline, UUID(int=1))
        if resolved.expected_result is None:
            assert by_key[case.key].outcome == "declined"
        else:
            domains.add(resolved.expected_result.operation)
            assert by_key[case.key].outcome == (
                "no_results" if resolved.expected_result.page.total == 0 else "answered"
            )
    assert len(domains) == 5
    assert {c.failure for c in answers.challenges} == {"unsupported_reference", "unsupported_fact"}


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "version",
        "missing",
        "duplicate",
        "unknown",
        "empty_fact",
        "challenge_source",
        "challenge_duplicate",
    ],
)
def test_invalid_expectations_are_rejected(tmp_path, mutation):
    data = json.loads(DEFAULT_ANSWERS.read_text())
    if mutation == "digest":
        data["query_dataset_sha256"] = "0" * 64
    if mutation == "version":
        data["query_dataset_version"] = "queries-unknown"
    if mutation == "missing":
        data["cases"].pop()
    if mutation == "duplicate":
        data["cases"].append(data["cases"][0])
    if mutation == "unknown":
        data["cases"][0]["query_case"] = "unknown"
    if mutation == "empty_fact":
        data["cases"][0]["required_facts"] = [" "]
    if mutation == "challenge_source":
        data["challenges"][0]["query_case"] = "unknown"
    if mutation == "challenge_duplicate":
        data["challenges"].append(data["challenges"][0])
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(data))
    with pytest.raises((ValueError, ValidationError)):
        load_answer_evaluation(path)
