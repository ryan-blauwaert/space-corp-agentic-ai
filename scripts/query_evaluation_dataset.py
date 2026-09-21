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

DEFAULT_EVALUATION = Path(__file__).resolve().parents[1] / "data/evaluations/queries-2.json"
_REFERENCE = re.compile(r"@[a-z_]+:[A-Za-z0-9_-]+")


class SupportedCase(Frozen):
    key: Key
    kind: Literal["supported"]
    question: str = Field(min_length=1, pattern=r"\S")
    expected_plan: dict[str, object]
    scenario_key: Key | None = None
    expected_result: dict[str, object] | None = None

    @model_validator(mode="after")
    def one_evidence_source(self) -> "SupportedCase":
        if (self.scenario_key is None) == (self.expected_result is None):
            raise ValueError("Provide a baseline scenario or authored result, exclusively")
        return self


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
    plan = QUERY_PLAN.validate_python(_resolve(case.expected_plan, manifest, workspace))
    if case.scenario_key is None:
        expected = case.expected_result
    else:
        scenario = next((s for s in manifest.scenarios if s.key == case.scenario_key), None)
        if scenario is None:
            raise ValueError("Unknown baseline scenario")
        expected = dict(scenario.expected)
        rows = expected.pop("rows")
        if not isinstance(rows, list):
            raise ValueError("Scenario rows must be a list")
        # Adapt baseline evidence to domain result shapes without deriving matching records.
        if scenario.question == "Q2" and expected["status"] == "no_unresolved_incident":
            expected["status"] = "no_incident_match"
        if scenario.question == "Q4":
            count = expected["count"]
            if not isinstance(count, int) or expected.pop("repeated") != (count >= 2):
                raise ValueError("Invalid canonical recurrence expectation")
        adapted = []
        for original in rows:
            row = dict(original)
            if scenario.question in ("Q3", "Q4", "Q5"):
                collection, identity = {
                    "Q3": (manifest.work_orders, "work_order_id"),
                    "Q4": (manifest.incidents, "incident_id"),
                    "Q5": (manifest.inventory, "inventory_id"),
                }[scenario.question]
                key = row[identity].split(":", 1)[1]
                record = next(item for item in collection if item.key == key)
                row["facility_id"] = f"@facilities:{record.model_dump()['facility']}"
                if scenario.question == "Q4":
                    incident = next(item for item in manifest.incidents if item.key == key)
                    row.update(
                        status=incident.status,
                        severity=incident.severity,
                        fault_code=incident.fault_code,
                    )
            adapted.append(row)
        expected.update(
            operation=plan.operation,
            page={"rows": adapted, "total": len(rows), "limit": 100, "offset": 0},
        )
    result = QUERY_RESULT.validate_python(_resolve(expected, manifest, workspace))
    if plan.operation != result.operation:
        raise ValueError("Expected plan and result operations must agree")
    return ResolvedCase(
        key=case.key,
        question=question,
        expected_plan=plan,
        expected_result=result,
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
    if {case.scenario_key for case in supported if case.scenario_key is not None} != {
        s.key for s in baseline.scenarios
    }:
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
