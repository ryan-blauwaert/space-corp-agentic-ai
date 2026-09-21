"""Exercise provisioning against a disposable cluster, never a developer database."""

import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.database import Database
from app.equipment.models import CatalogReleaseRecord, EquipmentModelRecord, EquipmentUnitRecord
from app.facilities.models import FacilityRecord
from app.operations.domain import (
    IncidentSeverity,
    IncidentStatus,
    WorkOrderPriority,
    WorkOrderStatus,
)
from app.operations.models import IncidentRecord, WorkOrderRecord
from app.operations.repository import SqlAlchemyIncidentRepository, SqlAlchemyWorkOrderRepository
from app.workspaces.models import WorkspaceRecord

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.integration


@pytest.fixture
def provisioning_cluster() -> Iterator[tuple[Path, dict[str, str]]]:
    binary_directory = os.getenv("SPACE_CORP_TEST_POSTGRES_BIN")
    if binary_directory is None:
        pytest.skip("SPACE_CORP_TEST_POSTGRES_BIN is not configured for disposable-cluster tests.")
    binaries = Path(binary_directory)
    with TemporaryDirectory(prefix="sc-pg-") as directory:
        root = Path(directory)
        data = root / "data"
        environment = dict(os.environ, PGHOST=directory, PGPORT="55439")
        # initdb defaults to the current OS user; avoid inherited connection options.
        for key in ("PGUSER", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS"):
            environment.pop(key, None)
        subprocess.run(
            [str(binaries / "initdb"), "-D", str(data), "-A", "trust", "--no-locale", "-E", "UTF8"],
            check=True,
            capture_output=True,
            env=environment,
        )
        subprocess.run(
            [
                str(binaries / "pg_ctl"),
                "-D",
                str(data),
                "-l",
                str(root / "server.log"),
                "-o",
                f"-k {directory} -h '' -p 55439",
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
            env=environment,
        )
        try:
            psql = binaries / "psql"
            for sql in (
                "CREATE ROLE space_corp LOGIN",
                "CREATE DATABASE space_corp OWNER space_corp",
                "CREATE DATABASE space_corp_test OWNER space_corp",
            ):
                subprocess.run(
                    [str(psql), "-X", "-d", "postgres", "-c", sql],
                    env=environment,
                    check=True,
                    capture_output=True,
                )
            for name in ("space_corp", "space_corp_test"):
                migration_environment = dict(
                    environment,
                    SPACE_CORP_MIGRATION_DATABASE_URL=(
                        f"postgresql+psycopg://space_corp@localhost/{name}?host={directory}&port=55439"
                    ),
                )
                subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=ROOT,
                    env=migration_environment,
                    check=True,
                    capture_output=True,
                )
            yield psql, environment
        finally:
            subprocess.run(
                [str(binaries / "pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop"],
                env=environment,
                check=True,
                capture_output=True,
            )


def sql(cluster: tuple[Path, dict[str, str]], statement: str) -> str:
    psql, environment = cluster
    return subprocess.run(
        [str(psql), "-X", "-At", "-v", "ON_ERROR_STOP=1", "-d", "space_corp", "-c", statement],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def provision(cluster: tuple[Path, dict[str, str]]) -> subprocess.CompletedProcess[str]:
    psql, environment = cluster
    return subprocess.run(
        [
            str(psql),
            "-X",
            "-d",
            "postgres",
            "-f",
            str(ROOT / "scripts/provision_postgresql_application_role.sql"),
        ],
        env=environment,
        capture_output=True,
        text=True,
    )


def sql_result(
    cluster: tuple[Path, dict[str, str]], statement: str
) -> subprocess.CompletedProcess[str]:
    psql, environment = cluster
    return subprocess.run(
        [
            str(psql),
            "-X",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            "space_corp",
            "-c",
            statement,
        ],
        env=environment,
        capture_output=True,
        text=True,
    )


def test_provisioning_removes_legacy_grants_and_is_repeatable(
    provisioning_cluster: tuple[Path, dict[str, str]],
) -> None:
    assert provision(provisioning_cluster).returncode == 0
    # Exercise both databases, table/column grants, and both levels of defaults.
    psql, environment = provisioning_cluster
    for database_name in ("space_corp", "space_corp_test"):
        subprocess.run(
            [
                str(psql),
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-d",
                database_name,
                "-c",
                "GRANT ALL ON ALL TABLES IN SCHEMA public TO PUBLIC, space_corp_app; "
                "GRANT UPDATE (reference_code) ON work_orders TO PUBLIC; "
                "GRANT UPDATE (fault_code) ON incidents TO space_corp_app; "
                "ALTER DEFAULT PRIVILEGES FOR ROLE space_corp GRANT ALL ON TABLES TO PUBLIC, space_corp_app; "
                "ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC, space_corp_app; "
                "ALTER DEFAULT PRIVILEGES FOR ROLE space_corp GRANT ALL ON SEQUENCES TO PUBLIC, space_corp_app; "
                "ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public GRANT ALL ON SEQUENCES TO PUBLIC, space_corp_app; "
                "SET ROLE space_corp; CREATE SEQUENCE legacy_sequence;",
            ],
            env=environment,
            check=True,
            capture_output=True,
        )
    sql(
        provisioning_cluster,
        "ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public GRANT ALL ON TABLES TO space_corp_app",
    )
    assert provision(provisioning_cluster).returncode == 0
    assert provision(provisioning_cluster).returncode == 0
    for database_name in ("space_corp", "space_corp_test"):
        result = subprocess.run(
            [
                str(psql),
                "-X",
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "-d",
                database_name,
                "-c",
                "SET ROLE space_corp; CREATE TABLE future_defaults_check (id integer); "
                "CREATE SEQUENCE future_sequence; "
                "SELECT has_column_privilege('space_corp_app', 'work_orders', 'reference_code', 'UPDATE'), "
                "has_column_privilege('space_corp_app', 'incidents', 'fault_code', 'UPDATE'), "
                "has_table_privilege('space_corp_app', 'work_orders', 'DELETE,TRUNCATE'), "
                "has_table_privilege('space_corp_app', 'future_defaults_check', 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE'), "
                "has_sequence_privilege('space_corp_app', 'legacy_sequence', 'USAGE,SELECT,UPDATE'), "
                "has_sequence_privilege('space_corp_app', 'future_sequence', 'USAGE,SELECT,UPDATE')",
            ],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.splitlines()[-1] == "f|f|f|f|f|f", database_name
    for privilege in ("SELECT", "INSERT"):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_table_privilege('space_corp_app', 'facilities', '{privilege}')",
            )
            == "t"
        )
    for column in ("name", "location", "operational_status", "updated_at"):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'facilities', "
                f"'{column}', 'UPDATE')",
            )
            == "t"
        )
    for column in ("workspace_id", "code", "facility_type", "id"):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'facilities', "
                f"'{column}', 'UPDATE')",
            )
            == "f"
        )
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'facilities', 'DELETE,TRUNCATE')",
        )
        == "f"
    )
    for privilege in ("SELECT", "INSERT"):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_table_privilege('space_corp_app', 'inventory_items', '{privilege}')",
            )
            == "t"
        )
    for column in ("quantity_on_hand", "reorder_point", "updated_at"):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'inventory_items', "
                f"'{column}', 'UPDATE')",
            )
            == "t"
        )
    for column in ("workspace_id", "facility_id", "component_id", "id"):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'inventory_items', "
                f"'{column}', 'UPDATE')",
            )
            == "f"
        )
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'inventory_items', 'DELETE,TRUNCATE')",
        )
        == "f"
    )
    for privilege in ("SELECT", "INSERT"):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_table_privilege('space_corp_app', 'incidents', '{privilege}')",
            )
            == "t"
        )
    for column in ("severity", "status", "resolved_at", "updated_at"):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_column_privilege('space_corp_app', 'incidents', '{column}', 'UPDATE')",
            )
            == "t"
        )
    for column in (
        "workspace_id",
        "facility_id",
        "equipment_unit_id",
        "reference_code",
        "fault_code",
    ):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_column_privilege('space_corp_app', 'incidents', '{column}', 'UPDATE')",
            )
            == "f"
        )
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'incidents', 'DELETE,TRUNCATE')",
        )
        == "f"
    )
    for privilege in ("SELECT", "INSERT"):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_table_privilege('space_corp_app', 'work_orders', '{privilege}')",
            )
            == "t"
        )
    for column in ("priority", "status", "due_at", "completed_at", "updated_at"):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'work_orders', "
                f"'{column}', 'UPDATE')",
            )
            == "t"
        )
    for column in (
        "workspace_id",
        "facility_id",
        "originating_incident_id",
        "target_equipment_unit_id",
        "reference_code",
    ):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'work_orders', "
                f"'{column}', 'UPDATE')",
            )
            == "f"
        )
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'work_orders', 'DELETE,TRUNCATE')",
        )
        == "f"
    )
    for table in (
        "catalog_releases",
        "equipment_models",
        "components",
        "equipment_model_components",
    ):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_table_privilege('space_corp_app', '{table}', 'SELECT')",
            )
            == "t"
        )
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_table_privilege('space_corp_app', '{table}', 'INSERT,UPDATE,DELETE,TRUNCATE')",
            )
            == "f"
        )
    for privilege in ("SELECT", "INSERT"):
        assert (
            sql(
                provisioning_cluster,
                f"SELECT has_table_privilege('space_corp_app', 'equipment_units', '{privilege}')",
            )
            == "t"
        )
    for column in ("operational_status", "updated_at"):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'equipment_units', "
                f"'{column}', 'UPDATE')",
            )
            == "t"
        )
    for column in ("workspace_id", "facility_id", "equipment_model_id", "asset_tag"):
        assert (
            sql(
                provisioning_cluster,
                "SELECT has_column_privilege("
                "'space_corp_app', 'equipment_units', "
                f"'{column}', 'UPDATE')",
            )
            == "f"
        )
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'equipment_units', 'DELETE,TRUNCATE')",
        )
        == "f"
    )
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'alembic_version', 'SELECT,INSERT,UPDATE,DELETE')",
        )
        == "f"
    )
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'workspaces', 'SELECT,INSERT,UPDATE,DELETE')",
        )
        == "f"
    )
    sql(provisioning_cluster, "SET ROLE space_corp; CREATE TABLE future_table (id integer)")
    assert (
        sql(
            provisioning_cluster,
            "SELECT has_table_privilege('space_corp_app', 'future_table', 'SELECT,INSERT,UPDATE,DELETE')",
        )
        == "f"
    )


def test_restricted_role_enforces_unit_and_inventory_rls_and_update_allowlists(
    provisioning_cluster: tuple[Path, dict[str, str]],
) -> None:
    first_workspace = "10000000-0000-4000-8000-000000000010"
    second_workspace = "10000000-0000-4000-8000-000000000020"
    first_facility = "10000000-0000-4000-8000-000000000011"
    second_facility = "10000000-0000-4000-8000-000000000021"
    catalog_release = "20000000-0000-4000-8000-000000000010"
    equipment_model = "21000000-0000-4000-8000-000000000010"
    equipment_unit = "22000000-0000-4000-8000-000000000010"
    component = "23000000-0000-4000-8000-000000000010"
    inventory_item = "24000000-0000-4000-8000-000000000010"
    work_order = "26000000-0000-4000-8000-000000000010"

    sql(
        provisioning_cluster,
        "SET ROLE space_corp; "
        f"INSERT INTO workspaces (id) VALUES ('{first_workspace}'), ('{second_workspace}'); "
        "INSERT INTO catalog_releases (id, code) "
        f"VALUES ('{catalog_release}', 'catalog-1'); "
        "INSERT INTO equipment_models (id, catalog_release_id, code, name) "
        f"VALUES ('{equipment_model}', '{catalog_release}', 'ECS-4', 'Environmental Control System 4'); "
        "INSERT INTO components (id, catalog_release_id, code, name) "
        f"VALUES ('{component}', '{catalog_release}', 'FLT-F12', 'Air Filter F-12'); "
        "INSERT INTO facilities "
        "(id, workspace_id, code, name, facility_type, location, operational_status) "
        f"VALUES ('{first_facility}', '{first_workspace}', 'LUN-OPS-01', 'Lunar Operations One', "
        "'lunar_installation', 'Mare Imbrium', 'operational'), "
        f"('{second_facility}', '{second_workspace}', 'LUN-OPS-01', 'Lunar Operations Two', "
        "'lunar_installation', 'Mare Serenitatis', 'operational')",
    )
    assert provision(provisioning_cluster).returncode == 0

    scoped_result = sql(
        provisioning_cluster,
        "SET ROLE space_corp_app; BEGIN; "
        f"SET LOCAL app.workspace_id = '{first_workspace}'; "
        "INSERT INTO equipment_units "
        "(id, workspace_id, facility_id, equipment_model_id, asset_tag, operational_status) "
        f"VALUES ('{equipment_unit}', '{first_workspace}', '{first_facility}', "
        f"'{equipment_model}', 'ECS-14', 'degraded'); "
        "UPDATE equipment_units SET operational_status = 'offline' "
        f"WHERE id = '{equipment_unit}'; "
        "INSERT INTO inventory_items "
        "(id, workspace_id, facility_id, component_id, quantity_on_hand, reorder_point) "
        f"VALUES ('{inventory_item}', '{first_workspace}', '{first_facility}', "
        f"'{component}', 0, 2); "
        "UPDATE inventory_items SET quantity_on_hand = 4, reorder_point = 5 "
        f"WHERE id = '{inventory_item}'; "
        "INSERT INTO work_orders "
        "(id, workspace_id, facility_id, target_equipment_unit_id, reference_code, priority, status) "
        f"VALUES ('{work_order}', '{first_workspace}', '{first_facility}', '{equipment_unit}', "
        "'WO-ECS-001', 'high', 'open'); "
        "UPDATE work_orders SET priority = 'critical', status = 'blocked' "
        f"WHERE id = '{work_order}'; "
        f"SELECT operational_status FROM equipment_units WHERE id = '{equipment_unit}'; "
        f"SELECT quantity_on_hand, reorder_point FROM inventory_items WHERE id = '{inventory_item}'; "
        f"SELECT priority, status FROM work_orders WHERE id = '{work_order}'; "
        "COMMIT",
    )
    assert "offline" in scoped_result.splitlines()
    assert "4|5" in scoped_result.splitlines()
    assert "critical|blocked" in scoped_result.splitlines()
    assert (
        sql(
            provisioning_cluster,
            "SET ROLE space_corp_app; SELECT count(*) FROM equipment_units",
        ).splitlines()[-1]
        == "0"
    )
    assert (
        sql(
            provisioning_cluster,
            "SET ROLE space_corp_app; SELECT count(*) FROM inventory_items",
        ).splitlines()[-1]
        == "0"
    )
    assert (
        sql_result(
            provisioning_cluster,
            "SET ROLE space_corp_app; BEGIN; "
            f"SET LOCAL app.workspace_id = '{first_workspace}'; "
            f"UPDATE work_orders SET reference_code = 'WO-CHANGED' WHERE id = '{work_order}'; COMMIT",
        ).returncode
        != 0
    )
    other_workspace_counts = sql(
        provisioning_cluster,
        "SET ROLE space_corp_app; BEGIN; "
        f"SET LOCAL app.workspace_id = '{second_workspace}'; "
        f"SELECT count(*) FROM equipment_units WHERE id = '{equipment_unit}'; "
        f"SELECT count(*) FROM inventory_items WHERE id = '{inventory_item}'; COMMIT",
    )
    assert other_workspace_counts.splitlines()[-3:-1] == ["0", "0"]
    assert (
        sql_result(
            provisioning_cluster,
            "SET ROLE space_corp_app; BEGIN; "
            f"SET LOCAL app.workspace_id = '{first_workspace}'; "
            "UPDATE equipment_units SET asset_tag = 'ECS-15' "
            f"WHERE id = '{equipment_unit}'; COMMIT",
        ).returncode
        != 0
    )
    assert (
        sql_result(
            provisioning_cluster,
            "SET ROLE space_corp_app; BEGIN; "
            f"SET LOCAL app.workspace_id = '{first_workspace}'; "
            "UPDATE inventory_items "
            f"SET component_id = '{component}' WHERE id = '{inventory_item}'; COMMIT",
        ).returncode
        != 0
    )
    assert (
        sql_result(
            provisioning_cluster,
            "SET ROLE space_corp_app; BEGIN; "
            f"SET LOCAL app.workspace_id = '{first_workspace}'; "
            "INSERT INTO inventory_items "
            "(id, workspace_id, facility_id, component_id, quantity_on_hand, reorder_point) "
            f"VALUES ('24000000-0000-4000-8000-000000000020', '{second_workspace}', "
            f"'{second_facility}', '{component}', 1, 1); COMMIT",
        ).returncode
        != 0
    )
    assert (
        sql_result(
            provisioning_cluster,
            "SET ROLE space_corp_app; BEGIN; "
            f"SET LOCAL app.workspace_id = '{first_workspace}'; "
            "INSERT INTO equipment_units "
            "(id, workspace_id, facility_id, equipment_model_id, asset_tag, operational_status) "
            f"VALUES ('22000000-0000-4000-8000-000000000020', '{second_workspace}', "
            f"'{second_facility}', '{equipment_model}', 'ECS-15', 'operational'); COMMIT",
        ).returncode
        != 0
    )


@pytest.mark.parametrize("unsafe_state", ["membership", "ownership", "missing_table"])
def test_provisioning_stops_before_grants_on_failed_preconditions(
    provisioning_cluster: tuple[Path, dict[str, str]], unsafe_state: str
) -> None:
    sql(provisioning_cluster, "CREATE ROLE space_corp_app LOGIN")
    if unsafe_state == "membership":
        sql(provisioning_cluster, "GRANT space_corp TO space_corp_app")
    elif unsafe_state == "ownership":
        sql(provisioning_cluster, "ALTER TABLE facilities OWNER TO CURRENT_USER")
    else:
        sql(provisioning_cluster, "DROP TABLE work_orders")
    result = provision(provisioning_cluster)
    assert result.returncode == 3
    assert "ERROR" in result.stderr
    # Inspect direct grants: the deliberately unsafe membership already inherits access.
    assert (
        sql(
            provisioning_cluster,
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE grantee = 'space_corp_app' AND table_schema = 'public'",
        )
        == "0"
    )


def test_operations_restricted_role_isolation_and_fixed_fields(
    provisioning_cluster: tuple[Path, dict[str, str]],
) -> None:
    """Verify real SQL and ORM updates under the same role used by the app."""
    _, environment = provisioning_cluster
    owner_url = URL.create(
        "postgresql+psycopg",
        username="space_corp",
        database="space_corp",
        host="localhost",
        query={"host": environment["PGHOST"], "port": environment["PGPORT"]},
    )
    owner = Database(owner_url.render_as_string(hide_password=False))
    application = Database(
        owner_url.set(username="space_corp_app").render_as_string(hide_password=False)
    )
    workspace_ids = [uuid4(), uuid4()]
    facility_ids = [uuid4(), uuid4()]
    unit_ids = [uuid4(), uuid4()]
    incident_ids = [uuid4(), uuid4()]
    work_order_ids = [uuid4(), uuid4()]
    release_id, model_id = uuid4(), uuid4()
    try:
        with owner.session() as session:
            session.add_all([WorkspaceRecord(id=value) for value in workspace_ids])
            session.add(CatalogReleaseRecord(id=release_id, code="acceptance"))
            session.flush()
            session.add(
                EquipmentModelRecord(
                    id=model_id, catalog_release_id=release_id, code="ECS", name="ECS"
                )
            )
            for workspace_id, facility_id in zip(workspace_ids, facility_ids, strict=True):
                session.add(
                    FacilityRecord(
                        id=facility_id,
                        workspace_id=workspace_id,
                        code="FAC-01",
                        name="Facility",
                        facility_type="lunar_installation",
                        location="Moon",
                        operational_status="operational",
                    )
                )
            session.flush()
            for workspace_id, facility_id, unit_id in zip(
                workspace_ids, facility_ids, unit_ids, strict=True
            ):
                session.add(
                    EquipmentUnitRecord(
                        id=unit_id,
                        workspace_id=workspace_id,
                        facility_id=facility_id,
                        equipment_model_id=model_id,
                        asset_tag="UNIT-01",
                        operational_status="operational",
                    )
                )
        assert provision(provisioning_cluster).returncode == 0

        # The restricted role itself creates records in both workspaces, with repeated codes.
        for index, workspace_id in enumerate(workspace_ids):
            with application.workspace_session(workspace_id) as session:
                session.add(
                    IncidentRecord(
                        id=incident_ids[index],
                        workspace_id=workspace_id,
                        facility_id=facility_ids[index],
                        equipment_unit_id=unit_ids[index],
                        reference_code="INC-01",
                        severity="high",
                        status="open",
                        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
                        fault_code="AIRFLOW",
                    )
                )
                session.flush()
                session.add(
                    WorkOrderRecord(
                        id=work_order_ids[index],
                        workspace_id=workspace_id,
                        facility_id=facility_ids[index],
                        originating_incident_id=incident_ids[index],
                        target_equipment_unit_id=unit_ids[index],
                        reference_code="WO-01",
                        priority="high",
                        status="open",
                    )
                )

        with application.workspace_session(workspace_ids[0]) as session:
            assert session.scalar(text("SELECT current_user")) == "space_corp_app"
            assert session.scalars(select(IncidentRecord.id)).all() == [incident_ids[0]]
            assert session.scalars(select(WorkOrderRecord.id)).all() == [work_order_ids[0]]
            for table, foreign_id in (
                ("incidents", incident_ids[1]),
                ("work_orders", work_order_ids[1]),
            ):
                result = session.execute(
                    text(f"UPDATE {table} SET status = 'open' WHERE id = :id"), {"id": foreign_id}
                )
                assert result.rowcount == 0

            resolved = SqlAlchemyIncidentRepository(session).update_lifecycle(
                workspace_ids[0],
                incident_ids[0],
                severity=IncidentSeverity.CRITICAL,
                status=IncidentStatus.RESOLVED,
                resolved_at=datetime.now(UTC),
            )
            completed = SqlAlchemyWorkOrderRepository(session).update_lifecycle(
                workspace_ids[0],
                work_order_ids[0],
                priority=WorkOrderPriority.CRITICAL,
                status=WorkOrderStatus.COMPLETED,
                due_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            assert resolved is not None and resolved.status is IncidentStatus.RESOLVED
            assert completed is not None and completed.status is WorkOrderStatus.COMPLETED

            fixed_columns = {
                "incidents": (
                    "id",
                    "workspace_id",
                    "facility_id",
                    "equipment_unit_id",
                    "reference_code",
                    "occurred_at",
                    "fault_code",
                    "created_at",
                ),
                "work_orders": (
                    "id",
                    "workspace_id",
                    "facility_id",
                    "originating_incident_id",
                    "target_equipment_unit_id",
                    "reference_code",
                    "created_at",
                ),
                "equipment_units": (
                    "id",
                    "workspace_id",
                    "facility_id",
                    "equipment_model_id",
                    "asset_tag",
                    "created_at",
                ),
            }
            for table, columns in fixed_columns.items():
                for column in columns:
                    assert_sqlstate(session, f"UPDATE {table} SET {column} = {column}", "42501")
            for table in (
                "facilities",
                "equipment_units",
                "inventory_items",
                "incidents",
                "work_orders",
            ):
                assert_sqlstate(session, f"DELETE FROM {table}", "42501")
                # CASCADE avoids mistaking an FK restriction for permission enforcement.
                assert_sqlstate(session, f"TRUNCATE {table} CASCADE", "42501")
            for statement in (
                "UPDATE incidents SET status = 'open'",
                "UPDATE incidents SET resolved_at = occurred_at - interval '1 second'",
                "UPDATE work_orders SET status = 'cancelled'",
                "UPDATE work_orders SET completed_at = created_at - interval '1 second'",
            ):
                assert_sqlstate(session, statement, "23514")
            assert_sqlstate(session, "UPDATE equipment_models SET name = 'Changed'", "42501")

            # RLS blocks foreign ownership; composite FKs block foreign references
            # even where a row claims the current workspace.
            incident_insert = (
                "INSERT INTO incidents (id, workspace_id, facility_id, equipment_unit_id, reference_code, severity, status, occurred_at) "
                "VALUES ('{id}', '{workspace}', '{facility}', '{unit}', 'INC-BAD', 'high', 'open', CURRENT_TIMESTAMP)"
            )
            work_insert = (
                "INSERT INTO work_orders (id, workspace_id, facility_id, originating_incident_id, target_equipment_unit_id, reference_code, priority, status) "
                "VALUES ('{id}', '{workspace}', '{facility}', '{incident}', '{unit}', 'WO-BAD', 'high', 'open')"
            )
            for template in (incident_insert, work_insert):
                values = dict(
                    id=uuid4(),
                    workspace=workspace_ids[1],
                    facility=facility_ids[1],
                    unit=unit_ids[1],
                    incident=incident_ids[1],
                )
                assert_sqlstate(session, template.format(**values), "42501")
                values.update(workspace=workspace_ids[0], facility=facility_ids[0])
                assert_sqlstate(session, template.format(**values), "23503")
            for field in ("unit", "incident"):
                values = dict(
                    id=uuid4(),
                    workspace=workspace_ids[0],
                    facility=facility_ids[0],
                    unit=unit_ids[0],
                    incident=incident_ids[0],
                )
                values[field] = unit_ids[1] if field == "unit" else incident_ids[1]
                assert_sqlstate(session, work_insert.format(**values), "23503")

        with application.session() as session:
            assert session.scalars(select(IncidentRecord.id)).all() == []
            assert session.scalars(select(WorkOrderRecord.id)).all() == []
            for template in (incident_insert, work_insert):
                values = dict(
                    id=uuid4(),
                    workspace=workspace_ids[0],
                    facility=facility_ids[0],
                    unit=unit_ids[0],
                    incident=incident_ids[0],
                )
                assert_sqlstate(session, template.format(**values), "42501")
        with application.workspace_session(workspace_ids[1]) as session:
            assert session.get(IncidentRecord, incident_ids[1]).status == "open"
            assert session.get(WorkOrderRecord, work_order_ids[1]).status == "open"
        # Owner repair remains available within the same relational constraints.
        with owner.session() as session:
            session.execute(
                text("UPDATE work_orders SET reference_code = 'REPAIRED' WHERE id = :id"),
                {"id": work_order_ids[0]},
            )
            assert session.get(WorkOrderRecord, work_order_ids[0]).reference_code == "REPAIRED"
    finally:
        application.dispose()
        owner.dispose()


def assert_sqlstate(session: Session, statement: str, expected: str) -> None:
    """Isolate expected SQL errors without aborting the surrounding scenario."""
    with pytest.raises(DBAPIError) as error:
        with session.begin_nested():
            session.execute(text(statement))
    assert error.value.orig.sqlstate == expected, statement
