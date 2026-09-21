from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from psycopg.errors import QueryCanceled
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from app.database import Database
from app.queries.contracts import FacilityEquipmentPlan, QueryContext, QueryPageRequest
from app.queries.equipment import EquipmentQueryExecutor
from app.queries.errors import QueryError, QueryErrorKind
from app.workspaces.models import WorkspaceRecord
from scripts.dataset_manifest import operational_id, shared_id
from scripts.query_evaluation_dataset import SupportedCase, load_evaluation, resolve_case


def context(workspace=None):
    return QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace or uuid4())


@pytest.mark.parametrize(
    "plan",
    [
        {},
        {"operation": "Q1"},
        {"operation": "inventory"},
        {"operation": "facility_equipment", "sql": "DROP TABLE incidents"},
        {"operation": "facility_equipment", "facility": {"workspace_id": str(uuid4())}},
        {"operation": "compatible_stock", "equipment_unit_id": "bad"},
        FacilityEquipmentPlan.model_construct(
            operation="facility_equipment", unit_statuses=("bogus",)
        ),
    ],
)
def test_invalid_or_unimplemented_plan_never_opens_database(plan):
    database = Mock(spec=Database)
    ctx = context()
    with pytest.raises(QueryError) as caught:
        EquipmentQueryExecutor(database).execute(ctx, plan)
    assert caught.value.kind == QueryErrorKind.INVALID_PLAN
    assert caught.value.context == ctx
    database.query_session.assert_not_called()


def test_invalid_page_cannot_bypass_validation():
    database = Mock(spec=Database)
    with pytest.raises(QueryError) as caught:
        EquipmentQueryExecutor(database).execute(
            context(),
            {"operation": "facility_equipment"},
            QueryPageRequest.model_construct(limit=100000, offset=0),
        )
    assert caught.value.kind == QueryErrorKind.INVALID_PLAN
    database.query_session.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, True, 10001, "10"])
def test_evidence_limit_is_bounded(limit):
    with pytest.raises(ValueError):
        EquipmentQueryExecutor(Mock(spec=Database), max_evidence=limit)


@pytest.mark.parametrize(
    "original,kind",
    [
        (QueryCanceled("secret SQL"), QueryErrorKind.TIMEOUT),
        (RuntimeError("secret URL"), QueryErrorKind.DATABASE_UNAVAILABLE),
    ],
)
def test_database_errors_are_sanitized(original, kind):
    database = Mock(spec=Database)

    @contextmanager
    def failed_session(*args, **kwargs):
        raise OperationalError("secret SQL", {}, original)
        yield

    database.query_session = failed_session
    with pytest.raises(QueryError) as caught:
        EquipmentQueryExecutor(database).execute(context(), {"operation": "facility_equipment"})
    assert caught.value.kind == kind
    assert "secret" not in str(caught.value)
    assert caught.value.__suppress_context__


@pytest.fixture
def seeded(query_data):
    app, owner, manifest, workspaces, extra_model, _ = query_data
    return EquipmentQueryExecutor(app), owner, manifest, workspaces, extra_model


CASES = [
    case
    for case in load_evaluation().cases
    if isinstance(case, SupportedCase)
    and case.expected_plan["operation"] in ("facility_equipment", "compatible_stock")
]


@pytest.mark.integration
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.key)
def test_canonical_and_extended_evidence_in_two_workspaces(seeded, case):
    executor, _, manifest, workspaces, _ = seeded
    for workspace in workspaces:
        expected = resolve_case(case, manifest, workspace)
        ctx = context(workspace)
        actual = executor.execute(ctx, expected.expected_plan, QueryPageRequest(limit=100))
        assert actual.context == ctx
        assert actual.catalog_release_id == shared_id(
            manifest.catalog.version, "release", manifest.catalog.version
        )
        assert actual.result == expected.expected_result


@pytest.mark.integration
@pytest.mark.parametrize(
    "field",
    [
        "facility",
        "unit",
        "model",
        "workspace",
        "unpinned",
        "foreign-facility",
        "foreign-unit",
        "wrong-release",
    ],
)
def test_missing_and_foreign_inputs_fail_as_not_found(seeded, field):
    executor, owner, manifest, workspaces, extra_model = seeded
    ctx = context(workspaces[0])
    plan = {"operation": "facility_equipment"}
    if field == "workspace":
        ctx = context()
    elif field == "unpinned":
        ctx = context()
        workspaces.append(ctx.workspace_id)
        with owner.session() as session:
            session.add(WorkspaceRecord(id=ctx.workspace_id))
    elif field in ("facility", "foreign-facility"):
        plan["facility"] = {
            "facility_id": uuid4()
            if field == "facility"
            else operational_id(workspaces[1], manifest.version, "facilities", "LUN-OPS-01")
        }
    elif field in ("unit", "foreign-unit"):
        plan = {
            "operation": "compatible_stock",
            "equipment_unit_id": uuid4()
            if field == "unit"
            else operational_id(workspaces[1], manifest.version, "units", "U001"),
        }
    else:
        plan["equipment_model_id"] = uuid4() if field == "model" else extra_model
    with pytest.raises(QueryError) as caught:
        executor.execute(ctx, plan)
    assert caught.value.kind == QueryErrorKind.NOT_FOUND


@pytest.mark.integration
def test_facility_filters_intersect_and_values_are_bound(seeded):
    executor, _, manifest, workspaces, _ = seeded
    ctx = context(workspaces[0])
    plan = {
        "operation": "facility_equipment",
        "facility": {"facility_type": "lunar_installation", "location": "Mare Imbrium"},
        "unit_statuses": ["offline"],
        "equipment_model_id": shared_id(manifest.catalog.version, "models", "M02"),
    }
    result = executor.execute(ctx, plan).result
    assert result.page.total == 1
    assert [u.unit_id for u in result.page.rows[0].units] == [
        operational_id(workspaces[0], manifest.version, "units", "U002")
    ]
    assert result.page.rows[0].incidents == ()
    plan["facility"]["facility_type"] = "orbital_station"
    assert executor.execute(ctx, plan).result.page.total == 0
    plan["facility"] = {"location": "Mare Imbrium' OR TRUE --"}
    assert executor.execute(ctx, plan).result.page.total == 0


@pytest.mark.integration
def test_resolved_incident_filter_and_omitted_statuses(seeded):
    executor, _, manifest, workspaces, _ = seeded
    ctx = context(workspaces[0])
    unit = operational_id(workspaces[0], manifest.version, "units", "U001")
    expected = operational_id(workspaces[0], manifest.version, "incidents", "I002")
    result = executor.execute(
        ctx,
        {
            "operation": "compatible_stock",
            "equipment_unit_id": unit,
            "incident_statuses": ["resolved"],
        },
    ).result
    assert result.incident_ids == (expected,)
    plan = {
        "operation": "facility_equipment",
        "equipment_model_id": shared_id(manifest.catalog.version, "models", "M01"),
        "facility": {
            "facility_id": operational_id(
                workspaces[0], manifest.version, "facilities", "LUN-OPS-01"
            )
        },
    }
    broad = executor.execute(ctx, plan).result.page.rows[0]
    assert expected in [i.incident_id for i in broad.incidents]
    plan["incident_statuses"] = ["resolved"]
    filtered = executor.execute(ctx, plan).result.page.rows[0]
    assert [i.incident_id for i in filtered.incidents] == [expected]
    assert [u.unit_id for u in filtered.units] == [unit]


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["facility_equipment", "compatible_stock"])
def test_pagination_preserves_totals_order_and_complete_nested_evidence(seeded, operation):
    executor, _, manifest, workspaces, _ = seeded
    ctx = context(workspaces[0])
    plan = {"operation": operation}
    if operation == "compatible_stock":
        plan["equipment_unit_id"] = operational_id(workspaces[0], manifest.version, "units", "U001")
    full = executor.execute(ctx, plan, QueryPageRequest(limit=100)).result
    rows = []
    for offset in range(full.page.total):
        page = executor.execute(ctx, plan, QueryPageRequest(limit=1, offset=offset)).result.page
        assert page.total == full.page.total
        rows.extend(page.rows)
    assert tuple(rows) == full.page.rows
    past = executor.execute(ctx, plan, QueryPageRequest(offset=full.page.total + 1)).result
    assert past.page.rows == () and past.page.total == full.page.total
    if operation == "compatible_stock":
        assert past.status == "matched"


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["facility_equipment", "compatible_stock"])
def test_excess_evidence_fails_without_silent_truncation(seeded, operation):
    executor, _, manifest, workspaces, _ = seeded
    ctx = context(workspaces[0])
    plan = {"operation": operation}
    if operation == "compatible_stock":
        plan.update(
            equipment_unit_id=operational_id(workspaces[0], manifest.version, "units", "U001"),
            incident_statuses=["open"],
        )
    with pytest.raises(QueryError) as caught:
        EquipmentQueryExecutor(executor.database, max_evidence=1).execute(ctx, plan)
    assert caught.value.kind == QueryErrorKind.RESOURCE_LIMIT
    assert executor.execute(ctx, plan).result.page.total > 0


@pytest.mark.integration
def test_executor_uses_read_only_session_and_resets_connection(seeded):
    executor, _, _, workspaces, _ = seeded
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(executor.database.engine, "before_cursor_execute", record)
    try:
        executor.execute(context(workspaces[0]), {"operation": "facility_equipment"})
    finally:
        event.remove(executor.database.engine, "before_cursor_execute", record)
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert all(s.startswith(("SELECT", "SET TRANSACTION")) for s in statements)
    from sqlalchemy import text

    with executor.database.session() as session:
        assert session.scalar(text("SELECT current_setting('app.workspace_id', true)")) in (
            None,
            "",
        )
        assert session.scalar(text("SHOW transaction_read_only")) == "off"


@pytest.mark.integration
def test_catalog_pin_function_is_scoped_without_workspace_table_access(seeded):
    executor, owner, manifest, workspaces, _ = seeded
    database = executor.database
    with database.query_session(workspaces[0]) as session:
        assert session.scalar(
            text("SELECT public.current_workspace_catalog_release()")
        ) == shared_id(manifest.catalog.version, "release", manifest.catalog.version)
        assert not session.scalar(
            text("SELECT has_table_privilege(current_user, 'public.workspaces', 'SELECT')")
        )
    with database.query_session(uuid4()) as session:
        assert session.scalar(text("SELECT public.current_workspace_catalog_release()")) is None
    with database.session() as session:
        assert session.scalar(text("SELECT public.current_workspace_catalog_release()")) is None
    with owner.session() as session:
        definition = session.execute(
            text(
                "SELECT prosecdef, proconfig, pronargs FROM pg_proc WHERE oid='public.current_workspace_catalog_release()'::regprocedure"
            )
        ).one()
        assert definition == (True, ["search_path=pg_catalog"], 0)
        assert not session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.oid='public.current_workspace_catalog_release()'::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE')"
            )
        )


@pytest.mark.integration
def test_pin_function_migration_round_trip(seeded):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    executor, owner, _, workspaces, _ = seeded
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    try:
        command.downgrade(config, "0010_baseline_pins")
        with owner.session() as session:
            assert (
                session.scalar(
                    text("SELECT to_regprocedure('public.current_workspace_catalog_release()')")
                )
                is None
            )
    finally:
        command.upgrade(config, "head")
        with owner.session() as session:
            session.execute(
                text(
                    "GRANT EXECUTE ON FUNCTION public.current_workspace_catalog_release() TO space_corp_app"
                )
            )
    assert (
        executor.execute(
            context(workspaces[0]), {"operation": "facility_equipment"}
        ).result.page.total
        == 5
    )
