"""Answer expectations layered on frozen query fixtures; no model or database calls."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.queries.contracts import Frozen
from scripts.dataset_manifest import Key, digest
from scripts.query_evaluation_dataset import DEFAULT_EVALUATION, load_evaluation

DEFAULT_ANSWERS = Path(__file__).resolve().parents[1] / "data/evaluations/answers-1.json"
Fact = Annotated[str, Field(min_length=1, pattern=r"\S")]


class AnswerExpectation(Frozen):
    query_case: Key
    outcome: Literal["answered", "no_results", "declined"]
    required_facts: tuple[Fact, ...] = Field(min_length=1)
    prohibited_claims: tuple[Fact, ...] = Field(min_length=1)


class GroundingChallenge(Frozen):
    key: Key
    query_case: Key
    candidate_claim: Fact
    failure: Literal["unsupported_reference", "unsupported_fact"]


class AnswerEvaluationDataset(Frozen):
    version: Key
    query_dataset_version: Key
    query_dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    purpose: Literal["development"] = "development"
    cases: tuple[AnswerExpectation, ...] = Field(min_length=1)
    challenges: tuple[GroundingChallenge, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_keys(self) -> "AnswerEvaluationDataset":
        if len({c.query_case for c in self.cases}) != len(self.cases):
            raise ValueError("Duplicate answer case")
        if len({c.key for c in self.challenges}) != len(self.challenges):
            raise ValueError("Duplicate grounding challenge")
        if not {c.query_case for c in self.challenges} <= {c.query_case for c in self.cases}:
            raise ValueError("Unknown grounding challenge source")
        return self


def load_answer_evaluation(
    path: Path = DEFAULT_ANSWERS, *, query_path: Path = DEFAULT_EVALUATION
) -> AnswerEvaluationDataset:
    queries = load_evaluation(query_path)
    answers = AnswerEvaluationDataset.model_validate_json(path.read_text())
    if answers.query_dataset_version != queries.version or answers.query_dataset_sha256 != digest(
        queries.model_dump(mode="json")
    ):
        raise ValueError("Answer expectations must match the frozen query dataset")
    if {c.query_case for c in answers.cases} != {c.key for c in queries.cases}:
        raise ValueError("Answer expectations must cover every query case exactly once")
    return answers
