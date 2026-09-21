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


def test_grounding_skips_database_without_uuid_mentions():
    from app.database import Database
    from app.queries.resolution import ground_references

    database = Mock(spec=Database)
    assert ground_references(database, context(uuid4()), "Stock at ZETA-DEPOT?") == {}
    database.query_session.assert_not_called()


def test_grounding_rejects_excess_mentions_before_database():
    from app.database import Database
    from app.queries.resolution import MAX_GROUNDED_REFERENCES, ground_references

    database = Mock(spec=Database)
    question = " ".join(str(uuid4()) for _ in range(MAX_GROUNDED_REFERENCES + 1))
    with pytest.raises(QueryError, match="invalid_plan"):
        ground_references(database, context(uuid4()), question)
    database.query_session.assert_not_called()


@pytest.mark.integration
def test_grounding_returns_only_literal_scoped_types_for_all_entity_kinds(query_data):
    from app.queries.resolution import ground_references

    database, _, manifest, workspaces, other_model, other_component = query_data
    workspace = workspaces[0]
    ids = {
        "facility": operational_id(workspace, manifest.version, "facilities", "LUN-OPS-01"),
        "unit": operational_id(workspace, manifest.version, "units", "U001"),
        "incident": operational_id(workspace, manifest.version, "incidents", "I001"),
        "model": shared_id(manifest.catalog.version, "models", "M01"),
        "component": shared_id(manifest.catalog.version, "components", "C01"),
    }
    hidden = [
        operational_id(workspaces[1], manifest.version, collection, key)
        for collection, key in [
            ("facilities", "LUN-OPS-01"),
            ("units", "U001"),
            ("incidents", "I001"),
        ]
    ] + [other_model, other_component, uuid4()]
    refs = [str(value) for value in [*ids.values(), *hidden]]
    question = ", ".join(refs + [refs[0]])
    hints = ground_references(database, context(workspace), question)
    assert hints == {
        **{str(value): [kind] for kind, value in ids.items()},
        **{str(v): [] for v in hidden},
    }
    # Literal spelling survives; no names, codes, or neighboring identifiers are added.
    assert ground_references(database, context(workspace), str(ids["unit"]).upper()) == {
        str(ids["unit"]).upper(): ["unit"]
    }
    assert ground_references(database, context(workspace), ids["model"].hex) == {
        ids["model"].hex: ["model"]
    }
    assert ground_references(database, context(workspace), "prefix_" + refs[0]) == {}


@pytest.mark.integration
def test_grounding_preserves_multiple_types_without_choosing(query_data):
    from app.queries.resolution import ground_references

    database, owner, manifest, workspaces, _, _ = query_data
    identifier = shared_id(manifest.catalog.version, "models", "M01")
    with owner.session() as session:
        session.add(
            FacilityRecord(
                id=identifier,
                workspace_id=workspaces[0],
                code="TYPE-COLLISION",
                name="Private label",
                location="Private location",
                facility_type="logistics_depot",
                operational_status="operational",
            )
        )
    assert ground_references(database, context(workspaces[0]), str(identifier)) == {
        str(identifier): ["facility", "model"]
    }


@pytest.mark.integration
def test_verified_type_reaches_planner_but_wrong_type_never_executes(query_data, caplog):
    import logging

    database, _, manifest, workspaces, _, _ = query_data
    identifier = str(shared_id(manifest.catalog.version, "components", "C01"))
    # Deliberately wrong field: identity hints never authorize automatic reinterpretation.
    subject, provider = service(
        database, json.dumps({"operation": "incidents", "equipment_unit_id": identifier})
    )
    subject.operations = Mock()
    with caplog.at_level(logging.INFO), pytest.raises(QueryError, match="not_found"):
        subject.ask(context(workspaces[0]), "Read records for " + identifier)
    assert len(provider.requests) == 1
    assert (
        json.dumps({identifier: ["component"]}, separators=(",", ":"))
        in provider.requests[0].prompt
    )
    subject.operations.execute.assert_not_called()
    assert identifier not in caplog.text
    assert '"event":"query_grounding"' in caplog.text


@pytest.mark.integration
@pytest.mark.parametrize(
    "collection,keys,shared",
    [
        ("facilities", ("LUN-OPS-01", "MCC-OPS-01"), False),
        ("units", ("U001", "U002"), False),
        ("incidents", ("I001", "I002"), False),
        ("models", ("M01", "M02"), True),
        ("components", ("C01", "C02"), True),
    ],
)
def test_multiple_scoped_candidates_cannot_be_silently_dropped(
    query_data, collection, keys, shared
):
    database, _, manifest, workspaces, _, _ = query_data
    identifiers = [
        shared_id(manifest.catalog.version, collection, key)
        if shared
        else operational_id(workspaces[0], manifest.version, collection, key)
        for key in keys
    ]
    question = "Records involving " + " or ".join(str(identifier) for identifier in identifiers)
    subject, provider = service(database, '{"operation":"inventory"}')
    subject.operations = Mock()
    subject.equipment = Mock()
    outcome = subject.ask(context(workspaces[0]), question)
    assert outcome.plan == DeclinedPlan(operation="declined", reason="ambiguous_input")
    assert outcome.response is None
    assert len(provider.requests) == 1
    subject.operations.execute.assert_not_called()
    subject.equipment.execute.assert_not_called()
    subject, _ = service(database, '{"operation":"declined","reason":"prohibited_operation"}')
    assert subject.ask(context(workspaces[0]), question).plan.reason == "prohibited_operation"
