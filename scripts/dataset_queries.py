"""Fixed reference queries for baseline acceptance, not a public query service."""

from datetime import UTC, datetime
from uuid import UUID
from typing import TypedDict, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.workspaces.models import WorkspaceRecord
from scripts.dataset_manifest import Manifest, operational_id, shared_id
from scripts.seed_support import SeedConfigurationError


class FacilityEvidence(TypedDict):
    facility_id: UUID
    units: list[dict[str, object]]
    incidents: list[dict[str, object]]


QUERIES = {
    "Q1": """SELECT f.id AS facility_id, u.id AS unit_id, i.id AS incident_id,
        u.operational_status, i.status AS incident_status
        FROM facilities f JOIN equipment_units u ON (u.workspace_id,u.facility_id)=(f.workspace_id,f.id)
        JOIN incidents i ON (i.workspace_id,i.equipment_unit_id)=(u.workspace_id,u.id)
        WHERE f.workspace_id=:workspace AND (CAST(:facility AS uuid) IS NULL OR f.id=:facility)
          AND u.operational_status IN ('degraded','offline') AND i.status IN ('open','investigating')
        ORDER BY f.code,u.asset_tag,i.reference_code""",
    "Q2": """SELECT m.id AS model_id, c.id AS component_id, stock.id AS inventory_id, stock.quantity_on_hand
        FROM equipment_units u JOIN equipment_models m ON u.equipment_model_id=m.id
        JOIN equipment_model_components link ON link.equipment_model_id=m.id
        JOIN components c ON c.id=link.component_id
        LEFT JOIN inventory_items stock ON (stock.workspace_id,stock.facility_id,stock.component_id)=(u.workspace_id,u.facility_id,c.id)
        WHERE u.workspace_id=:workspace AND u.id=:unit AND m.catalog_release_id=:release
        ORDER BY c.code""",
    "Q3": """SELECT w.id AS work_order_id, w.status, w.priority, w.due_at,
        COALESCE(w.due_at < :as_of,FALSE) AS overdue, w.status='blocked' AS blocked,
        w.originating_incident_id, i.equipment_unit_id AS incident_equipment_unit_id, w.target_equipment_unit_id
        FROM work_orders w LEFT JOIN incidents i ON (i.workspace_id,i.id)=(w.workspace_id,w.originating_incident_id)
        WHERE w.workspace_id=:workspace AND w.facility_id=:facility
          AND w.priority IN ('high','critical') AND w.status IN ('open','in_progress','blocked')
        ORDER BY w.reference_code""",
    "Q4": """SELECT i.id AS incident_id, u.id AS unit_id, u.facility_id, i.occurred_at
        FROM incidents i JOIN equipment_units u ON (u.workspace_id,u.id)=(i.workspace_id,i.equipment_unit_id)
        WHERE i.workspace_id=:workspace AND u.equipment_model_id=:model AND i.fault_code=:fault
          AND i.occurred_at >= :window_start AND i.occurred_at < :as_of
        ORDER BY i.reference_code""",
    "Q5": """SELECT stock.id AS inventory_id, stock.component_id, stock.quantity_on_hand,
        stock.reorder_point, stock.reorder_point-stock.quantity_on_hand AS shortfall
        FROM inventory_items stock JOIN components c ON c.id=stock.component_id
        WHERE stock.workspace_id=:workspace AND stock.facility_id=:facility
          AND stock.quantity_on_hand < stock.reorder_point AND c.catalog_release_id=:release
        ORDER BY c.code""",
}


def json_value(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_value(v) for v in value]
    return value


def evaluate(session: Session, workspace_id: UUID, manifest: Manifest, question: str, inputs: dict[str, str]) -> dict[str, object]:
    workspace = session.get(WorkspaceRecord, workspace_id)
    release = shared_id(manifest.catalog.version, "release", manifest.catalog.version)
    baseline = shared_id(manifest.version, "baseline", manifest.version)
    if workspace is None or (workspace.baseline_id, workspace.catalog_release_id) != (baseline, release):
        raise SeedConfigurationError("Queries require a matching pinned workspace.")
    parameters = dict(workspace=workspace_id, release=release, as_of=manifest.as_of,
                      window_start=manifest.window_start, facility=None)
    for key, entity in (("facility", "facilities"), ("unit", "units")):
        if key in inputs:
            parameters[key] = operational_id(workspace_id, manifest.version, entity, inputs[key])
            table = "facilities" if key == "facility" else "equipment_units"
            if session.scalar(text(f"SELECT id FROM {table} WHERE workspace_id=:workspace AND id=:{key}"), parameters) is None:
                raise SeedConfigurationError("Requested input does not exist in this workspace.")
    if "model" in inputs:
        parameters["model"] = shared_id(manifest.catalog.version, "models", inputs["model"])
        if session.scalar(text("SELECT id FROM equipment_models WHERE id=:model AND catalog_release_id=:release"), parameters) is None:
            raise SeedConfigurationError("Unknown model in the pinned release.")
    parameters["fault"] = inputs.get("fault_code", "").strip().upper()
    incident_ids = []
    if question == "Q2":
        incident_ids = list(session.scalars(text("SELECT id FROM incidents WHERE workspace_id=:workspace AND equipment_unit_id=:unit AND status IN ('open','investigating') ORDER BY reference_code"), parameters))
        if not incident_ids:
            return {"status": "no_unresolved_incident", "incident_ids": [], "rows": []}
    rows = [dict(row) for row in session.execute(text(QUERIES[question]), parameters).mappings()]
    result: dict[str, object] = {"rows": rows}
    if question == "Q1":
        grouped: dict[UUID, FacilityEvidence] = {}
        for row in rows:
            evidence = grouped.setdefault(row["facility_id"], FacilityEvidence(facility_id=row["facility_id"], units=[], incidents=[]))
            unit = dict(unit_id=row["unit_id"], operational_status=row["operational_status"])
            if unit not in evidence["units"]:
                evidence["units"].append(unit)
            evidence["incidents"].append(dict(incident_id=row["incident_id"], equipment_unit_id=row["unit_id"], status=row["incident_status"]))
        result = {"rows": list(grouped.values())}
    elif question == "Q2":
        result.update(status="matched" if rows else "no_compatibility", incident_ids=incident_ids)
    elif question == "Q4":
        result.update(count=len(rows), repeated=len(rows) >= 2)
    return cast(dict[str, object], json_value(result))


def expected_evidence(value: object, workspace: UUID, manifest: Manifest) -> object:
    if isinstance(value, str) and value.startswith("@"):
        entity, key = value[1:].split(":", 1)
        id_ = shared_id(manifest.catalog.version, entity, key) if entity in ("models", "components") else operational_id(workspace, manifest.version, entity, key)
        return str(id_)
    if isinstance(value, dict):
        return {k: expected_evidence(v, workspace, manifest) for k, v in value.items()}
    if isinstance(value, list):
        return [expected_evidence(v, workspace, manifest) for v in value]
    return value


def validate_scenarios(session: Session, workspace: UUID, manifest: Manifest) -> int:
    for scenario in manifest.scenarios:
        actual = evaluate(session, workspace, manifest, scenario.question, scenario.inputs)
        expected = expected_evidence(scenario.expected, workspace, manifest)
        if actual != expected:
            raise SeedConfigurationError(f"Scenario {scenario.key} failed: expected {expected!r}, received {actual!r}")
    return len(manifest.scenarios)
