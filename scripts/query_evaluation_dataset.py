"""Load versioned question fixtures without model calls or database access."""

import re
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.queries.contracts import (
    QUERY_PLAN,
    QUERY_RESULT,
    DeclinedPlan,
    Frozen,
    PlanningOutcome,
    QueryResult,
)
from scripts.dataset_manifest import Key, Manifest, digest, load_manifest, operational_id, shared_id

DEFAULT_EVALUATION = Path(__file__).resolve().parents[1] / "data/evaluations/queries-1.json"
_REFERENCE = re.compile(r"@[a-z_]+:[A-Za-z0-9_-]+")


class SupportedCase(Frozen):
    key: Key
    kind: Literal["supported"]
    question: str = Field(min_length=1, pattern=r"\S")
    scenario_key: Key


class DeclinedCase(Frozen):
    key: Key
    kind: Literal["declined"]
    question: str = Field(min_length=1, pattern=r"\S")
    expected: DeclinedPlan


EvaluationCase = Annotated[SupportedCase | DeclinedCase, Field(discriminator="kind")]


class EvaluationDataset(Frozen):
    version: Key
    baseline_version: Key
    baseline_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    catalog_version: Key
    prohibited_behaviors: tuple[
        Literal["writes", "cross_workspace_reads", "raw_sql_execution", "unvalidated_execution"],
        ...,
    ] = Field(min_length=1)
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases(self) -> "EvaluationDataset":
        if len({case.key for case in self.cases}) != len(self.cases):
            raise ValueError("Evaluation case keys must be unique")
        if (
            set(self.prohibited_behaviors)
            != {"writes", "cross_workspace_reads", "raw_sql_execution", "unvalidated_execution"}
            or len(self.prohibited_behaviors) != 4
        ):
            raise ValueError("All four prohibited behaviors must be specified exactly once")
        return self


class ResolvedCase(Frozen):
    key: Key
    question: str = Field(repr=False)
    expected_plan: PlanningOutcome
    expected_result: QueryResult | None = Field(repr=False)
    execution_allowed: bool


def _reference(reference: str, manifest: Manifest, workspace: UUID) -> str:
    entity, key = reference[1:].split(":", 1)
    collections = {
        "facilities": manifest.facilities,
        "units": manifest.units,
        "inventory": manifest.inventory,
        "incidents": manifest.incidents,
        "work_orders": manifest.work_orders,
        "models": manifest.catalog.models,
        "components": manifest.catalog.components,
    }
    if entity not in collections or key not in {item.key for item in collections[entity]}:
        raise ValueError("Unknown baseline evidence reference")
    if entity in ("models", "components"):
        return str(shared_id(manifest.catalog.version, entity, key))
    return str(operational_id(workspace, manifest.version, entity, key))


def _resolve(value: object, manifest: Manifest, workspace: UUID) -> object:
    if isinstance(value, str) and value.startswith("@"):
        return _reference(value, manifest, workspace)
    if isinstance(value, list):
        return [_resolve(item, manifest, workspace) for item in value]
    if isinstance(value, dict):
        return {key: _resolve(item, manifest, workspace) for key, item in value.items()}
    return value


def resolve_case(case: EvaluationCase, manifest: Manifest, workspace: UUID) -> ResolvedCase:
    """Resolve authored fixture identities; never compute expectations from SQL results."""
    question = _REFERENCE.sub(
        lambda match: _reference(match[0], manifest, workspace), case.question
    )
    if isinstance(case, DeclinedCase):
        return ResolvedCase(
            key=case.key,
            question=question,
            expected_plan=case.expected,
            expected_result=None,
            execution_allowed=False,
        )
    scenario = next((s for s in manifest.scenarios if s.key == case.scenario_key), None)
    if scenario is None:
        raise ValueError("Unknown baseline scenario")
    plan: dict[str, object] = {"operation": scenario.question}
    for source, target, collection in (
        ("facility", "facility_id", "facilities"),
        ("unit", "equipment_unit_id", "units"),
        ("model", "equipment_model_id", "models"),
    ):
        if source in scenario.inputs:
            plan[target] = _reference(
                f"@{collection}:{scenario.inputs[source]}", manifest, workspace
            )
    if scenario.question in ("Q3", "Q4"):
        plan["as_of"] = manifest.as_of
    if scenario.question == "Q4":
        plan.update(window_start=manifest.window_start, fault_code=scenario.inputs["fault_code"])
    expected = dict(scenario.expected)
    rows = expected.pop("rows")
    if not isinstance(rows, list):
        raise ValueError("Scenario rows must be a list")
    expected.update(
        operation=scenario.question,
        page={
            "rows": rows,
            "total": len(rows),
            "limit": 100,
            "offset": 0,
        },
    )
    return ResolvedCase(
        key=case.key,
        question=question,
        expected_plan=QUERY_PLAN.validate_python(plan),
        expected_result=QUERY_RESULT.validate_python(_resolve(expected, manifest, workspace)),
        execution_allowed=True,
    )


def load_evaluation(
    path: Path = DEFAULT_EVALUATION, *, manifest: Manifest | None = None
) -> EvaluationDataset:
    baseline = manifest if manifest is not None else load_manifest()
    dataset = EvaluationDataset.model_validate_json(path.read_text())
    if (
        dataset.baseline_version != baseline.version
        or dataset.catalog_version != baseline.catalog.version
        or dataset.baseline_sha256 != digest(baseline.model_dump(mode="json"))
    ):
        raise ValueError("Evaluation baseline version, catalog, or digest mismatch")
    supported = [case for case in dataset.cases if isinstance(case, SupportedCase)]
    if {case.scenario_key for case in supported} != {s.key for s in baseline.scenarios}:
        raise ValueError("Evaluation must cover every baseline scenario")
    if {case.expected.reason for case in dataset.cases if isinstance(case, DeclinedCase)} != {
        "unsupported_question",
        "prohibited_operation",
        "missing_input",
        "ambiguous_input",
    }:
        raise ValueError("Evaluation must cover each declined-planning outcome")
    for case in dataset.cases:
        resolve_case(case, baseline, UUID(int=1))
    return dataset
