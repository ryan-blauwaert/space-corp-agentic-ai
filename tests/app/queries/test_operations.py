from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from psycopg.errors import QueryCanceled
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from app.database import Database
from app.equipment.models import equipment_model_components
from app.queries.contracts import InventoryPlan, QueryContext, QueryPageRequest
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.operations import OperationsQueryExecutor
from scripts.dataset_manifest import operational_id, shared_id
from scripts.query_evaluation_dataset import (
    SupportedCase,
    evidence_matches,
    load_evaluation,
    resolve_case,
)

NOW = "2026-01-31T12:00:00Z"
START = "2026-01-01T00:00:00Z"


def context(workspace=None):
    return QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace or uuid4())


@pytest.fixture
def seeded(query_data):
    app, owner, manifest, workspaces, model, component = query_data
    return OperationsQueryExecutor(app), owner, manifest, workspaces, model, component


def record_id(seeded, collection, key, workspace=0):
    return operational_id(seeded[3][workspace], seeded[2].version, collection, key)


def catalog_id(seeded, collection, key):
    return shared_id(seeded[2].catalog.version, collection, key)


def execute(seeded, plan, **page):
    return seeded[0].execute(context(seeded[3][0]), plan, QueryPageRequest(**page)).result


def local_plan(seeded, operation):
    result = {
        "operation": operation,
        "facility": {"facility_id": record_id(seeded, "facilities", "LUN-OPS-01")},
    }
    if operation == "work_orders":
        result["as_of"] = NOW
    return result


@pytest.mark.parametrize(
    "plan",
    [
        {},
        {"operation": "Q3"},
        {"operation": "facility_equipment"},
        {"operation": "work_orders"},
        {"operation": "incidents", "statuses": []},
        {"operation": "inventory", "quantity": {"operator": "eq", "value": True}},
        {"operation": "inventory", "sql": "secret SELECT"},
        {"operation": "incidents", "facility": {"workspace_id": str(uuid4())}},
        InventoryPlan.model_construct(operation="inventory", below_reorder_point="yes"),
    ],
)
def test_invalid_and_wrong_domain_plan_rejected_before_database(plan):
    database = Mock(spec=Database)
    with pytest.raises(QueryError) as error:
        OperationsQueryExecutor(database).execute(context(), plan)
    assert error.value.kind == QueryErrorKind.INVALID_PLAN
    database.query_session.assert_not_called()


@pytest.mark.parametrize("operation", ["work_orders", "incidents", "inventory"])
@pytest.mark.parametrize("timeout", [False, True])
def test_operational_database_failure_is_sanitized(operation, timeout):
    database = Mock(spec=Database)

    @contextmanager
    def fail(*args, **kwargs):
        raise OperationalError(
            "secret SQL", {}, QueryCanceled("secret") if timeout else RuntimeError("secret URL")
        )
        yield

    database.query_session = fail
    plan = {"operation": operation}
    if operation == "work_orders":
        plan["as_of"] = NOW
    ctx = context()
    with pytest.raises(QueryError) as error:
        OperationsQueryExecutor(database).execute(ctx, plan)
    assert error.value.kind == (
        QueryErrorKind.TIMEOUT if timeout else QueryErrorKind.DATABASE_UNAVAILABLE
    )
    assert error.value.context == ctx
    assert "secret" not in str(error.value)


CASES = [
    c
    for c in load_evaluation().cases
    if isinstance(c, SupportedCase)
    and c.expected_plan["operation"] in ("work_orders", "incidents", "inventory")
]


@pytest.mark.integration
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.key)
def test_all_remaining_canonical_and_extended_cases_in_two_workspaces(seeded, case):
    executor, _, manifest, workspaces, _, _ = seeded
    for workspace in workspaces:
        expected = resolve_case(case, manifest, workspace)
        ctx = context(workspace)
        actual = executor.execute(ctx, expected.expected_plan, QueryPageRequest(limit=100))
        assert actual.context == ctx
        assert actual.catalog_release_id == shared_id(
            manifest.catalog.version, "release", manifest.catalog.version
        )
        assert evidence_matches(actual.result, expected.expected_result)


@pytest.mark.integration
@pytest.mark.parametrize(
    "overdue,keys",
    [
        (True, ["W001", "W006"]),
        (False, ["W002", "W003", "W004", "W005", "W007", "W008", "W009", "W010", "W011", "W012"]),
    ],
)
def test_due_boundary_unscheduled_closed_and_priority_independence(seeded, overdue, keys):
    plan = {**local_plan(seeded, "work_orders"), "overdue": overdue}
    result = execute(seeded, plan)
    assert [r.work_order_id for r in result.page.rows] == [
        record_id(seeded, "work_orders", k) for k in keys
    ]
    assert all(r.overdue is overdue for r in result.page.rows)


@pytest.mark.integration
def test_work_filters_intersect_and_keep_incident_and_target_separate(seeded):
    plan = {
        **local_plan(seeded, "work_orders"),
        "statuses": ["blocked", "open"],
        "priorities": ["critical"],
        "originating_incident_id": record_id(seeded, "incidents", "I001"),
        "target_equipment_unit_id": record_id(seeded, "units", "U002"),
    }
    (row,) = execute(seeded, plan).page.rows
    assert row.work_order_id == record_id(seeded, "work_orders", "W001")
    assert row.incident_equipment_unit_id == record_id(seeded, "units", "U001")
    assert row.target_equipment_unit_id == record_id(seeded, "units", "U002")
    assert row.blocked and row.overdue
    plan["priorities"] = ["low"]
    assert execute(seeded, plan).page.total == 0
    plan["priorities"] = ["critical"]
    plan["target_equipment_unit_id"] = record_id(seeded, "units", "U001")
    assert execute(seeded, plan).page.total == 0  # No implicit incident-unit fallback.


@pytest.mark.integration
def test_facility_level_incidents_and_missing_faults_remain_visible(seeded):
    result = execute(seeded, local_plan(seeded, "incidents"))
    rows = {r.incident_id: r for r in result.page.rows}
    assert rows[record_id(seeded, "incidents", "I006")].unit_id is None
    assert rows[record_id(seeded, "incidents", "I005")].fault_code is None
    assert result.count == 7
    plan = {
        **local_plan(seeded, "incidents"),
        "equipment_unit_id": record_id(seeded, "units", "U001"),
        "equipment_model_id": catalog_id(seeded, "models", "M01"),
        "statuses": ["open"],
        "severities": ["high"],
        "fault_code": " airflow ",
        "occurred": {"start": START, "end": NOW},
    }
    filtered = execute(seeded, plan)
    assert [r.incident_id for r in filtered.page.rows] == [record_id(seeded, "incidents", "I001")]
    plan["severities"] = ["low", "medium"]
    assert execute(seeded, plan).count == 0
    plan["severities"] = ["high"]
    plan["equipment_model_id"] = catalog_id(seeded, "models", "M02")
    assert execute(seeded, plan).count == 0


@pytest.mark.integration
def test_incident_counts_ignore_originating_work_order_fanout_and_page_size(seeded):
    plan = {
        "operation": "incidents",
        "equipment_model_id": catalog_id(seeded, "models", "M01"),
        "fault_code": "AIRFLOW",
        "occurred": {"start": START, "end": NOW},
    }
    result = execute(seeded, plan, limit=1)
    assert result.count == result.page.total == 2
    assert len(result.page.rows) == 1
    assert result.page.rows[0].incident_id == record_id(seeded, "incidents", "I001")
    assert execute(seeded, plan, limit=1, offset=1).page.rows[0].incident_id == record_id(
        seeded, "incidents", "I002"
    )
    assert execute(seeded, plan, offset=2).count == 2


@pytest.mark.integration
@pytest.mark.parametrize(
    "operator,keys",
    [
        ("lt", ["C01", "C02"]),
        ("lte", ["C01", "C02", "C04"]),
        ("eq", ["C04"]),
        ("gte", [f"C{i:02}" for i in range(4, 37)]),
        ("gt", [f"C{i:02}" for i in range(5, 37)]),
    ],
)
def test_quantity_comparison_operators_including_equality(seeded, operator, keys):
    plan = {**local_plan(seeded, "inventory"), "quantity": {"operator": operator, "value": 5}}
    assert [r.component_id for r in execute(seeded, plan).page.rows] == [
        catalog_id(seeded, "components", k) for k in keys
    ]


@pytest.mark.integration
def test_inventory_filters_zero_missing_surplus_and_compatibility_deduplication(seeded):
    executor, owner, manifest, workspaces, _, _ = seeded
    plan = {
        **local_plan(seeded, "inventory"),
        "compatible_model_id": catalog_id(seeded, "models", "M01"),
    }
    rows = execute(seeded, plan).page.rows
    assert [r.quantity_on_hand for r in rows] == [3, 0]  # C03 absent, not zero.
    assert [r.shortfall for r in rows] == [2, 2]
    plan.update(component_id=catalog_id(seeded, "components", "C03"))
    assert execute(seeded, plan).page.total == 0
    plan["component_id"] = catalog_id(seeded, "components", "C01")
    plan["below_reorder_point"] = False
    assert execute(seeded, plan).page.total == 0
    plan = {
        **local_plan(seeded, "inventory"),
        "compatible_model_id": catalog_id(seeded, "models", "M02"),
        "below_reorder_point": False,
    }
    assert [r.shortfall for r in execute(seeded, plan).page.rows] == [0, 0, 0]
    # Multiple model links must not multiply stock rows for the requested model.
    with owner.session() as session:
        session.execute(
            equipment_model_components.insert().values(
                catalog_release_id=shared_id(
                    manifest.catalog.version, "release", manifest.catalog.version
                ),
                equipment_model_id=catalog_id(seeded, "models", "M03"),
                component_id=catalog_id(seeded, "components", "C04"),
            )
        )
    try:
        assert execute(seeded, plan).page.total == 3
    finally:
        with owner.session() as session:
            session.execute(
                equipment_model_components.delete().where(
                    equipment_model_components.c.equipment_model_id
                    == catalog_id(seeded, "models", "M03"),
                    equipment_model_components.c.component_id
                    == catalog_id(seeded, "components", "C04"),
                )
            )


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["work_orders", "incidents", "inventory"])
def test_common_facility_filters_and_hostile_literal(seeded, operation):
    plan = local_plan(seeded, operation)
    plan["facility"].update(facility_type="lunar_installation", location="Mare Imbrium")
    assert execute(seeded, plan).page.total > 0
    plan["facility"]["facility_type"] = "orbital_station"
    assert execute(seeded, plan).page.total == 0
    plan["facility"] = {"location": "Mare Imbrium' OR TRUE --"}
    assert execute(seeded, plan).page.total == 0


REFS = [
    ("work_orders", "target_equipment_unit_id", "units", "U001"),
    ("work_orders", "originating_incident_id", "incidents", "I001"),
    ("incidents", "equipment_unit_id", "units", "U001"),
    ("incidents", "equipment_model_id", "models", "M01"),
    ("inventory", "component_id", "components", "C01"),
    ("inventory", "compatible_model_id", "models", "M01"),
]


@pytest.mark.integration
@pytest.mark.parametrize("operation,field,collection,key", REFS)
@pytest.mark.parametrize("other", [False, True])
def test_missing_foreign_and_wrong_revision_references_fail_before_empty_result(
    seeded, operation, field, collection, key, other
):
    plan = local_plan(seeded, operation)
    if not other:
        ref = uuid4()
    elif collection in ("models", "components"):
        ref = seeded[4] if collection == "models" else seeded[5]
    else:
        ref = record_id(seeded, collection, key, workspace=1)
    plan[field] = ref
    plan["facility"]["location"] = "No matches anyway"
    with pytest.raises(QueryError) as caught:
        execute(seeded, plan)
    assert caught.value.kind == QueryErrorKind.NOT_FOUND


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["work_orders", "incidents", "inventory"])
@pytest.mark.parametrize("foreign", [False, True])
def test_facility_reference_validation(seeded, operation, foreign):
    plan = local_plan(seeded, operation)
    plan["facility"]["facility_id"] = (
        record_id(seeded, "facilities", "LUN-OPS-01", workspace=1) if foreign else uuid4()
    )
    with pytest.raises(QueryError) as caught:
        execute(seeded, plan)
    assert caught.value.kind == QueryErrorKind.NOT_FOUND


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["work_orders", "incidents", "inventory"])
def test_paging_stable_with_distinct_totals_and_empty_later_page(seeded, operation):
    plan = local_plan(seeded, operation)
    full = execute(seeded, plan, limit=100)
    rows = []
    for offset in range(0, full.page.total, 3):
        paged = execute(seeded, plan, limit=3, offset=offset)
        assert paged.page.total == full.page.total
        rows.extend(paged.page.rows)
    assert tuple(rows) == full.page.rows
    assert execute(seeded, plan, offset=full.page.total).page.rows == ()


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["work_orders", "incidents", "inventory"])
def test_read_only_transaction_and_unscoped_pool_reset(seeded, operation):
    database = seeded[0].database
    statements = []

    def record(conn, cursor, statement, parameters, ctx, many):
        statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", record)
    try:
        execute(seeded, local_plan(seeded, operation))
    finally:
        event.remove(database.engine, "before_cursor_execute", record)
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert all(s.startswith(("SELECT", "SET TRANSACTION")) for s in statements)
    assert len(statements) <= 8
    with database.session() as session:
        assert session.scalar(text("SELECT current_setting('app.workspace_id', true)")) in (
            None,
            "",
        )
        assert session.scalar(text("SHOW transaction_read_only")) == "off"
