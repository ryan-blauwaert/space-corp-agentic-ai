import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.queries.contracts import (
    PLANNING_OUTCOME,
    QUERY_PLAN,
    QUERY_RESULT,
    CompatibleStockEvidence,
    EvidencePage,
    FacilityConditionEvidence,
    FaultOccurrenceEvidence,
    FaultRecurrenceResult,
    PriorityWorkEvidence,
    QueryContext,
    QueryPageRequest,
    QueryResponse,
    StockShortfallEvidence,
)

ID = str(UUID(int=1))
OTHER = str(UUID(int=2))
NOW = "2026-01-31T12:00:00Z"
START = "2026-01-01T00:00:00Z"
PLANS = [
    {"operation": "Q1"},
    {"operation": "Q1", "facility_id": ID},
    {"operation": "Q2", "equipment_unit_id": ID},
    {"operation": "Q3", "facility_id": ID, "as_of": NOW},
    {
        "operation": "Q4",
        "equipment_model_id": ID,
        "fault_code": "AIRFLOW",
        "window_start": START,
        "as_of": NOW,
    },
    {"operation": "Q5", "facility_id": ID},
]


@pytest.mark.parametrize("data", PLANS)
def test_plans_round_trip(data):
    plan = QUERY_PLAN.validate_json(json.dumps(data))
    assert QUERY_PLAN.validate_json(plan.model_dump_json()) == plan
    assert PLANNING_OUTCOME.validate_json(plan.model_dump_json()) == plan
    with pytest.raises(ValidationError):
        plan.operation = "Q5"


@pytest.mark.parametrize("data", PLANS)
@pytest.mark.parametrize(
    "extra", ["workspace_id", "catalog_release_id", "sql", "where", "limit", "offset", "request_id"]
)
def test_model_cannot_add_scope_sql_or_caller_controls(data, extra):
    with pytest.raises(ValidationError):
        QUERY_PLAN.validate_python({**data, extra: ID})


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"operation": "Q6"},
        {"operation": "DROP TABLE"},
        {"operation": "Q2"},
        {"operation": "Q3", "facility_id": ID},
        {"operation": "Q5", "facility_id": None},
        {"operation": "Q2", "equipment_unit_id": "unit-name"},
        {
            "operation": "Q4",
            "equipment_model_id": ID,
            "fault_code": " ",
            "window_start": START,
            "as_of": NOW,
        },
        {
            "operation": "Q4",
            "equipment_model_id": ID,
            "fault_code": "x" * 65,
            "window_start": START,
            "as_of": NOW,
        },
    ],
)
def test_invalid_or_missing_inputs_fail(data):
    with pytest.raises(ValidationError):
        QUERY_PLAN.validate_python(data)


@pytest.mark.parametrize(
    "start,end",
    [
        (NOW, NOW),
        (NOW, START),
        ("2026-01-01T00:00:00", NOW),
        (START, "2026-01-31T12:00:00"),
        ("yesterday", NOW),
    ],
)
def test_invalid_windows_fail(start, end):
    with pytest.raises(ValidationError):
        QUERY_PLAN.validate_python({**PLANS[4], "window_start": start, "as_of": end})


def test_fault_normalization_and_utc_instants():
    plan = QUERY_PLAN.validate_python(
        {**PLANS[4], "fault_code": " airflow ", "as_of": "2026-01-31T07:00:00-05:00"}
    )
    assert plan.fault_code == "AIRFLOW"
    assert plan.as_of == datetime(2026, 1, 31, 12, tzinfo=UTC)
    assert plan.as_of.tzinfo is UTC


@pytest.mark.parametrize(
    "reason", ["unsupported_question", "prohibited_operation", "missing_input", "ambiguous_input"]
)
def test_declined_plan_cannot_be_used_as_executable_plan(reason):
    data = {"operation": "declined", "reason": reason}
    assert PLANNING_OUTCOME.validate_python(data).reason == reason
    with pytest.raises(ValidationError):
        QUERY_PLAN.validate_python(data)
    with pytest.raises(ValidationError):
        PLANNING_OUTCOME.validate_python({**data, "sql": "SELECT 1"})


@pytest.mark.parametrize(
    "limits",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": True},
        {"limit": "20"},
        {"offset": -1},
        {"offset": 0.5},
        {"offset": False},
    ],
)
def test_page_bounds_are_strict(limits):
    with pytest.raises(ValidationError):
        QueryPageRequest(**limits)


def test_page_is_immutable_and_keeps_total_separate_from_page_size():
    page = EvidencePage[int](rows=[1], total=8, offset=2, limit=1)
    assert page.rows == (1,)
    assert page.total == 8
    with pytest.raises(ValidationError):
        page.total = 9
    for invalid in [
        dict(rows=[1, 2], total=8, limit=1),
        dict(rows=[1], total=1, offset=1),
        dict(rows=[], total=-1),
    ]:
        with pytest.raises(ValidationError):
            EvidencePage[int](**invalid)
    assert EvidencePage[int](rows=[], total=1, offset=5).rows == ()


def test_facility_evidence_matches_incidents_to_distinct_units():
    data = dict(
        facility_id=ID,
        units=[dict(unit_id=ID, operational_status="degraded")],
        incidents=[dict(incident_id=ID, equipment_unit_id=ID, status="open")],
    )
    result = FacilityConditionEvidence(**data)
    assert isinstance(result.units, tuple)
    for changes in [
        dict(units=[]),
        dict(units=data["units"] * 2),
        dict(incidents=data["incidents"] * 2),
        dict(incidents=[dict(incident_id=ID, equipment_unit_id=OTHER, status="open")]),
    ]:
        with pytest.raises(ValidationError):
            FacilityConditionEvidence(**{**data, **changes})


@pytest.mark.parametrize("inventory,quantity", [(ID, 0), (ID, 2), (None, None)])
def test_stock_preserves_zero_and_unknown(inventory, quantity):
    row = CompatibleStockEvidence(
        model_id=ID, component_id=OTHER, inventory_id=inventory, quantity_on_hand=quantity
    )
    assert row.quantity_on_hand == quantity


@pytest.mark.parametrize("inventory,quantity", [(None, 0), (ID, None), (ID, -1), (ID, True)])
def test_invalid_inventory_evidence_fails(inventory, quantity):
    with pytest.raises(ValidationError):
        CompatibleStockEvidence(
            model_id=ID, component_id=ID, inventory_id=inventory, quantity_on_hand=quantity
        )


@pytest.mark.parametrize(
    "status,incidents,total",
    [
        ("no_unresolved_incident", [], 0),
        ("no_compatibility", [ID], 0),
        ("matched", [ID], 2),
    ],
)
def test_q2_status_and_empty_page_semantics(status, incidents, total):
    data = dict(
        operation="Q2",
        status=status,
        incident_ids=incidents,
        page=dict(rows=[], total=total, offset=total),
    )
    assert QUERY_RESULT.validate_python(data).status == status
    with pytest.raises(ValidationError):
        QUERY_RESULT.validate_python({**data, "incident_ids": [ID] if not incidents else []})


def work(**overrides):
    return dict(
        work_order_id=ID,
        status="blocked",
        priority="high",
        due_at=NOW,
        overdue=True,
        blocked=True,
        originating_incident_id=ID,
        incident_equipment_unit_id=ID,
        target_equipment_unit_id=OTHER,
        **overrides,
    )


def test_work_evidence_keeps_distinct_units_and_optional_references():
    row = PriorityWorkEvidence(**work())
    assert row.incident_equipment_unit_id != row.target_equipment_unit_id
    data = work()
    data.update(
        originating_incident_id=None,
        incident_equipment_unit_id=None,
        target_equipment_unit_id=None,
        due_at=None,
        overdue=False,
    )
    assert PriorityWorkEvidence(**data).due_at is None


@pytest.mark.parametrize(
    "overrides",
    [
        dict(blocked=False),
        dict(due_at=None),
        dict(originating_incident_id=None),
        dict(status="completed"),
        dict(priority="low"),
        dict(overdue="true"),
    ],
)
def test_invalid_work_evidence_fails(overrides):
    with pytest.raises(ValidationError):
        PriorityWorkEvidence(**{**work(), **overrides})


def test_recurrence_uses_total_count_not_page_length():
    row = FaultOccurrenceEvidence(incident_id=ID, unit_id=ID, facility_id=ID, occurred_at=START)
    page = EvidencePage[FaultOccurrenceEvidence](rows=[row], total=2, limit=1)
    result = FaultRecurrenceResult(operation="Q4", count=2, repeated=True, page=page)
    assert len(result.page.rows) == 1
    for changes in [dict(count=1), dict(repeated=False), dict(repeated="true")]:
        with pytest.raises(ValidationError):
            FaultRecurrenceResult(**{**result.model_dump(), **changes})
    with pytest.raises(ValidationError):
        FaultRecurrenceResult(
            operation="Q4", count=2, repeated=True, page=dict(rows=[row, row], total=2)
        )


@pytest.mark.parametrize("quantity,reorder,shortfall", [(3, 5, 2), (0, 2, 2)])
def test_shortfall_evidence(quantity, reorder, shortfall):
    row = StockShortfallEvidence(
        inventory_id=ID,
        component_id=OTHER,
        quantity_on_hand=quantity,
        reorder_point=reorder,
        shortfall=shortfall,
    )
    assert row.shortfall == shortfall


@pytest.mark.parametrize(
    "quantity,reorder,shortfall", [(2, 2, 0), (5, 2, -3), (1, 5, 2), (True, 2, 1)]
)
def test_non_shortfall_or_incorrect_evidence_rejected(quantity, reorder, shortfall):
    with pytest.raises(ValidationError):
        StockShortfallEvidence(
            inventory_id=ID,
            component_id=OTHER,
            quantity_on_hand=quantity,
            reorder_point=reorder,
            shortfall=shortfall,
        )


def test_response_preserves_caller_context_and_catalog():
    context = QueryContext(request_id=ID, operation_id=OTHER, workspace_id=ID)
    response = QueryResponse(
        context=context,
        catalog_release_id=OTHER,
        result=dict(operation="Q5", page=dict(rows=[], total=0)),
    )
    assert QueryResponse.model_validate_json(response.model_dump_json()) == response
    assert response.context == context
    assert response.catalog_release_id == UUID(OTHER)
    assert "rows" not in repr(response)
