import json
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.facilities.models import FacilityRecord
from app.queries.contracts import DeclinedPlan, QueryContext
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.planning import parse_plan
from app.queries.resolution import resolve_plan
from scripts.dataset_manifest import operational_id, shared_id
from tests.app.queries.test_service import service


def context(workspace):
    return QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace)


@pytest.mark.integration
@pytest.mark.parametrize(
    "proposal,collection,key,field,shared",
    [
        (
            {"operation": "inventory", "facility": {"facility_id": "Lunar Operations One"}},
            "facilities",
            "LUN-OPS-01",
            "facility_id",
            False,
        ),
        (
            {"operation": "inventory", "facility": {"facility_id": "lun-ops-01"}},
            "facilities",
            "LUN-OPS-01",
            "facility_id",
            False,
        ),
        (
            {"operation": "compatible_stock", "equipment_unit_id": "U001"},
            "units",
            "U001",
            "equipment_unit_id",
            False,
        ),
        (
            {"operation": "facility_equipment", "equipment_model_id": "M01"},
            "models",
            "M01",
            "equipment_model_id",
            True,
        ),
        (
            {"operation": "inventory", "component_id": "C01"},
            "components",
            "C01",
            "component_id",
            True,
        ),
        (
            {"operation": "inventory", "compatible_model_id": "M01"},
            "models",
            "M01",
            "compatible_model_id",
            True,
        ),
        (
            {"operation": "incidents", "equipment_model_id": "M01"},
            "models",
            "M01",
            "equipment_model_id",
            True,
        ),
        (
            {"operation": "incidents", "equipment_unit_id": "U001"},
            "units",
            "U001",
            "equipment_unit_id",
            False,
        ),
        (
            {
                "operation": "work_orders",
                "target_equipment_unit_id": "U001",
                "as_of": "2026-01-31T12:00:00Z",
            },
            "units",
            "U001",
            "target_equipment_unit_id",
            False,
        ),
        (
            {
                "operation": "work_orders",
                "originating_incident_id": "I001",
                "as_of": "2026-01-31T12:00:00Z",
            },
            "incidents",
            "I001",
            "originating_incident_id",
            False,
        ),
    ],
)
def test_exact_codes_names_and_pinned_catalog(query_data, proposal, collection, key, field, shared):
    database, _, manifest, workspaces, _, _ = query_data
    for workspace in workspaces:
        ctx = context(workspace)
        text = json.dumps(proposal)
        resolved = resolve_plan(database, ctx, parse_plan(text, text, ctx))
        actual = (
            resolved.facility.facility_id if field == "facility_id" else getattr(resolved, field)
        )
        expected = (
            shared_id(manifest.catalog.version, collection, key)
            if shared
            else operational_id(workspace, manifest.version, collection, key)
        )
        assert actual == expected


@pytest.mark.integration
@pytest.mark.parametrize(
    "kind",
    [
        "foreign_facility",
        "foreign_unit",
        "foreign_incident",
        "model",
        "component",
        "unknown",
        "injection",
    ],
)
def test_unavailable_references_fail_without_evidence_execution(query_data, kind):
    database, _, manifest, workspaces, model, component = query_data
    ctx = context(workspaces[0])
    proposal = {"operation": "inventory"}
    if kind == "foreign_facility":
        value = operational_id(workspaces[1], manifest.version, "facilities", "LUN-OPS-01")
        proposal["facility"] = {"facility_id": str(value)}
    elif kind in ("foreign_unit", "foreign_incident"):
        is_unit = kind == "foreign_unit"
        value = operational_id(
            workspaces[1],
            manifest.version,
            "units" if is_unit else "incidents",
            "U001" if is_unit else "I001",
        )
        proposal = {
            "operation": "work_orders",
            "as_of": "2026-01-31T12:00:00Z",
            "target_equipment_unit_id" if is_unit else "originating_incident_id": str(value),
        }
    else:
        proposal["compatible_model_id" if kind == "model" else "component_id"] = (
            str(model)
            if kind == "model"
            else str(component)
            if kind == "component"
            else "C01' OR TRUE --"
            if kind == "injection"
            else "missing-component"
        )
    text = json.dumps(proposal)
    subject, _ = service(database, text)
    subject.equipment = Mock()
    subject.operations = Mock()
    with pytest.raises(QueryError) as error:
        subject.ask(ctx, text)
    assert error.value.kind == QueryErrorKind.NOT_FOUND
    subject.equipment.execute.assert_not_called()
    subject.operations.execute.assert_not_called()


@pytest.mark.integration
def test_ambiguous_name_is_declined_without_evidence_execution(query_data):
    database, owner, _, workspaces, _, _ = query_data
    with owner.session() as session:
        session.execute(
            update(FacilityRecord)
            .where(FacilityRecord.workspace_id == workspaces[0])
            .values(name="Shared name")
        )
    text = json.dumps({"operation": "inventory", "facility": {"facility_id": "Shared name"}})
    subject, _ = service(database, text)
    subject.operations = Mock()
    outcome = subject.ask(context(workspaces[0]), "Stock at Shared name?")
    assert isinstance(outcome.plan, DeclinedPlan)
    assert outcome.plan.reason == "ambiguous_input"
    assert outcome.response is None
    subject.operations.execute.assert_not_called()


@pytest.mark.integration
def test_resolution_failure_trace_omits_reference(query_data, caplog):
    import logging

    database = query_data[0]
    reference = "private-missing-entity"
    subject, _ = service(
        database, json.dumps({"operation": "inventory", "component_id": reference})
    )
    with caplog.at_level(logging.INFO), pytest.raises(QueryError, match="not_found"):
        subject.ask(context(query_data[3][0]), reference)
    events = [json.loads(r.message) for r in caplog.records if r.name == "app.queries.service"]
    assert events[-1]["event"] == "query_resolution"
    assert events[-1]["error_kind"] == "not_found"
    assert reference not in caplog.text
    assert "query_execution" not in caplog.text
