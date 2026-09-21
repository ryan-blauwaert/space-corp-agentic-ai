from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import (
    Database,
    DatabaseConfigurationError,
    create_database,
    create_database_engine,
)
from app.facilities.domain import FacilityOperationalStatus, FacilityType, NewFacility
from app.facilities.models import FacilityRecord
from app.facilities.repository import SqlAlchemyFacilityRepository
from app.workspaces.models import WorkspaceRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_create_database_engine_uses_psycopg_driver() -> None:
    engine = create_database_engine("postgresql://localhost/space_corp_test")

    try:
        assert isinstance(engine, Engine)
        assert engine.url.drivername == "postgresql+psycopg"
    finally:
        engine.dispose()


def test_create_database_engine_rejects_unsupported_postgresql_driver() -> None:
    with pytest.raises(DatabaseConfigurationError, match="Psycopg driver"):
        create_database_engine("postgresql+asyncpg://localhost/space_corp_test")


def test_database_creates_sessions_without_connecting() -> None:
    database = Database("postgresql://localhost/space_corp_test")

    try:
        with database.session() as session:
            assert session.bind is database.engine
    finally:
        database.dispose()


def test_database_session_commits_and_closes_on_success() -> None:
    database = Database("postgresql://localhost/space_corp_test")
    session = Mock(spec=Session)
    database.session_factory = Mock(return_value=session)

    try:
        with database.session() as returned_session:
            assert returned_session is session

        session.commit.assert_called_once_with()
        session.rollback.assert_not_called()
        session.close.assert_called_once_with()
    finally:
        database.dispose()


def test_database_session_rolls_back_and_closes_on_failure() -> None:
    database = Database("postgresql://localhost/space_corp_test")
    session = Mock(spec=Session)
    database.session_factory = Mock(return_value=session)

    try:
        with pytest.raises(ValueError, match="test failure"):
            with database.session():
                raise ValueError("test failure")

        session.commit.assert_not_called()
        session.rollback.assert_called_once_with()
        session.close.assert_called_once_with()
    finally:
        database.dispose()


def test_workspace_session_sets_transaction_local_workspace_context() -> None:
    database = Database("postgresql://localhost/space_corp_test")
    session = Mock(spec=Session)
    database.session_factory = Mock(return_value=session)
    workspace_id = uuid4()

    try:
        with database.workspace_session(workspace_id) as returned_session:
            assert returned_session is session

        statement = session.execute.call_args.args[0]
        parameters = session.execute.call_args.args[1]
        assert "set_config('app.workspace_id'" in str(statement)
        assert parameters == {"workspace_id": str(workspace_id)}
        session.commit.assert_called_once_with()
    finally:
        database.dispose()


def make_new_facility(code: str) -> NewFacility:
    return NewFacility(
        code=code,
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )


def test_create_database_requires_configured_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPACE_CORP_DATABASE_URL", raising=False)

    with pytest.raises(DatabaseConfigurationError, match="SPACE_CORP_DATABASE_URL"):
        create_database(Settings(_env_file=None))


@pytest.mark.integration
def test_postgresql_connection(integration_application_database_url: str) -> None:
    engine = create_database_engine(integration_application_database_url)

    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


@pytest.mark.integration
def test_migrations_apply(integration_migration_database_url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_database_engine(integration_migration_database_url)

    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert revision == "0011_query_catalog_pin"
    finally:
        engine.dispose()


@pytest.mark.integration
def test_migrations_match_persistence_models(
    integration_migration_database_url: str,
) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    command.check(config)


@pytest.mark.integration
@pytest.mark.usefixtures("preserve_application_grants")
def test_component_catalog_migration_downgrades_and_reapplies(
    integration_migration_database_url: str,
) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0005_catalog_equipment_units")
        engine = create_database_engine(integration_migration_database_url)

        try:
            with engine.connect() as connection:
                component_table, compatibility_table = connection.execute(
                    text(
                        "SELECT to_regclass('public.components'), "
                        "to_regclass('public.equipment_model_components')"
                    )
                ).one()

            assert component_table is None
            assert compatibility_table is None
        finally:
            engine.dispose()
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.usefixtures("preserve_application_grants")
def test_inventory_migration_downgrades_and_reapplies(
    integration_migration_database_url: str,
) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0006_components_compatibility")
        engine = create_database_engine(integration_migration_database_url)

        try:
            with engine.connect() as connection:
                inventory_table = connection.execute(
                    text("SELECT to_regclass('public.inventory_items')")
                ).scalar_one()

            assert inventory_table is None
        finally:
            engine.dispose()
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
def test_workspace_catalog_and_equipment_tables_exist(
    integration_migration_database_url: str,
) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_database_engine(integration_migration_database_url)

    try:
        with engine.connect() as connection:
            table_names = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN ("
                        "'workspaces', 'facilities', 'catalog_releases', "
                        "'equipment_models', 'components', "
                        "'equipment_model_components', 'equipment_units', "
                        "'inventory_items', 'incidents', 'work_orders'"
                        ")"
                    )
                ).scalars()
            )

        assert table_names == {
            "workspaces",
            "facilities",
            "catalog_releases",
            "components",
            "equipment_model_components",
            "equipment_models",
            "equipment_units",
            "inventory_items",
            "incidents",
            "work_orders",
        }
    finally:
        engine.dispose()


@pytest.mark.integration
def test_application_role_enforces_workspace_rls_and_resets_pooled_context(
    integration_application_database_url: str,
    integration_migration_database_url: str,
) -> None:
    """Verify the restricted login role cannot bypass Facility RLS."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    application_database = Database(integration_application_database_url)
    migration_database = Database(integration_migration_database_url)
    first_workspace_id = uuid4()
    second_workspace_id = uuid4()

    try:
        with migration_database.session() as session:
            session.add_all(
                [
                    WorkspaceRecord(id=first_workspace_id),
                    WorkspaceRecord(id=second_workspace_id),
                ]
            )

        with migration_database.session() as session:
            bypass_rls, is_superuser, can_create_role, can_create_database = session.execute(
                text(
                    "SELECT rolbypassrls, rolsuper, rolcreaterole, rolcreatedb "
                    "FROM pg_roles WHERE rolname = 'space_corp_app'"
                )
            ).one()

            table_owners = dict(
                session.execute(
                    text(
                        "SELECT relation.relname, owner.rolname "
                        "FROM pg_class AS relation "
                        "JOIN pg_namespace AS schema "
                        "ON schema.oid = relation.relnamespace "
                        "JOIN pg_roles AS owner ON owner.oid = relation.relowner "
                        "WHERE schema.nspname = 'public' "
                        "AND relation.relname IN ("
                        "'workspaces', 'facilities', 'catalog_releases', "
                        "'equipment_models', 'components', "
                        "'equipment_model_components', 'equipment_units', "
                        "'inventory_items', 'incidents', 'work_orders'"
                        ")"
                    )
                ).all()
            )
            role_memberships = (
                session.execute(
                    text(
                        "SELECT granted_role.rolname "
                        "FROM pg_auth_members AS membership "
                        "JOIN pg_roles AS member ON member.oid = membership.member "
                        "JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid "
                        "WHERE member.rolname = 'space_corp_app'"
                    )
                )
                .scalars()
                .all()
            )

        assert (bypass_rls, is_superuser, can_create_role, can_create_database) == (
            False,
            False,
            False,
            False,
        )
        assert table_owners == {
            "catalog_releases": "space_corp",
            "components": "space_corp",
            "equipment_model_components": "space_corp",
            "equipment_models": "space_corp",
            "equipment_units": "space_corp",
            "facilities": "space_corp",
            "inventory_items": "space_corp",
            "incidents": "space_corp",
            "work_orders": "space_corp",
            "workspaces": "space_corp",
        }
        assert role_memberships == []

        connection_ids: list[int] = []
        with application_database.workspace_session(first_workspace_id) as session:
            assert session.execute(text("SELECT current_user")).scalar_one() == ("space_corp_app")
            connection_ids.append(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
            first_facility = SqlAlchemyFacilityRepository(session).create(
                first_workspace_id, make_new_facility("LUN-OPS-01")
            )

        with application_database.workspace_session(second_workspace_id) as session:
            connection_ids.append(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
            second_facility = SqlAlchemyFacilityRepository(session).create(
                second_workspace_id, make_new_facility("ORB-OPS-01")
            )

        assert connection_ids[0] == connection_ids[1]

        with application_database.workspace_session(first_workspace_id) as session:
            assert session.get(FacilityRecord, second_facility.id) is None
            assert (
                session.execute(
                    update(FacilityRecord)
                    .where(FacilityRecord.id == second_facility.id)
                    .values(name="Should not update")
                ).rowcount
                == 0
            )
            assert session.execute(select(FacilityRecord.id)).scalars().all() == [first_facility.id]

        with pytest.raises(ProgrammingError):
            with application_database.workspace_session(first_workspace_id) as session:
                SqlAlchemyFacilityRepository(session).create(
                    second_workspace_id, make_new_facility("ORB-OPS-02")
                )

        with application_database.session() as session:
            final_connection_id = session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            assert session.execute(select(FacilityRecord.id)).scalars().all() == []
            assert session.execute(
                text("SELECT current_setting('app.workspace_id', true)")
            ).scalar_one() in (None, "")

        assert final_connection_id == connection_ids[0]
    finally:
        with migration_database.session() as session:
            session.execute(
                delete(FacilityRecord).where(
                    FacilityRecord.workspace_id.in_([first_workspace_id, second_workspace_id])
                )
            )
            session.execute(
                delete(WorkspaceRecord).where(
                    WorkspaceRecord.id.in_([first_workspace_id, second_workspace_id])
                )
            )
        application_database.dispose()
        migration_database.dispose()


@pytest.mark.integration
@pytest.mark.usefixtures("preserve_application_grants")
def test_required_text_migration_rejects_existing_invalid_data_without_rewriting_it(
    integration_migration_database_url: str,
) -> None:
    from sqlalchemy.exc import IntegrityError

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    database = Database(integration_migration_database_url)
    workspace_id = uuid4()
    facility_id = uuid4()
    try:
        command.downgrade(config, "0003_facility_workspace_rls")
        with database.session() as session:
            # This intentionally targets the pre-baseline schema. Do not use
            # today's ORM workspace columns to construct historical test data.
            session.execute(text("INSERT INTO workspaces (id) VALUES (:id)"), {"id": workspace_id})
            session.add(
                FacilityRecord(
                    id=facility_id,
                    workspace_id=workspace_id,
                    code=" ",
                    name="Legacy",
                    facility_type="orbital_station",
                    location="Orbit",
                    operational_status="operational",
                )
            )
        with pytest.raises(IntegrityError):
            command.upgrade(config, "head")
        with database.session() as session:
            assert session.get(FacilityRecord, facility_id).code == " "
            assert (
                session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0003_facility_workspace_rls"
            )
            session.get(FacilityRecord, facility_id).code = "LEGACY-01"
        command.upgrade(config, "head")
        with database.session() as session:
            assert session.get(FacilityRecord, facility_id).code == "LEGACY-01"
    finally:
        with database.session() as session:
            session.execute(delete(FacilityRecord).where(FacilityRecord.id == facility_id))
            session.execute(delete(WorkspaceRecord).where(WorkspaceRecord.id == workspace_id))
        database.dispose()
        command.upgrade(config, "head")


@pytest.fixture
def preserve_application_grants(
    migrated_database: str,
    integration_application_database_url: str,
) -> Iterator[None]:
    """Round-trip migrations must not leave the shared test role unprovisioned."""
    from sqlalchemy.engine import make_url

    database = Database(migrated_database)
    role = make_url(integration_application_database_url).username
    quote = database.engine.dialect.identifier_preparer.quote_identifier
    try:
        with database.session() as session:
            tables = session.execute(
                text("""
                SELECT table_name, privilege_type, is_grantable
                FROM information_schema.role_table_grants
                WHERE table_schema = 'public' AND grantee = :role
            """),
                {"role": role},
            ).all()
            columns = session.execute(
                text("""
                SELECT table_name, column_name, privilege_type, is_grantable
                FROM information_schema.column_privileges
                WHERE table_schema = 'public' AND grantee = :role
            """),
                {"role": role},
            ).all()
        yield
    finally:
        with database.session() as session:
            for table, privilege, grantable in tables:
                suffix = " WITH GRANT OPTION" if grantable == "YES" else ""
                session.execute(
                    text(f"GRANT {privilege} ON public.{quote(table)} TO {quote(role)}{suffix}")
                )
            table_privileges = {(table, privilege) for table, privilege, _ in tables}
            for table, column, privilege, grantable in columns:
                if (table, privilege) not in table_privileges:
                    suffix = " WITH GRANT OPTION" if grantable == "YES" else ""
                    session.execute(
                        text(
                            f"GRANT {privilege} ({quote(column)}) ON public.{quote(table)} TO {quote(role)}{suffix}"
                        )
                    )
        database.dispose()


@pytest.mark.parametrize("workspace", [None, "", "not-a-uuid", str(uuid4()), 1])
def test_query_session_requires_trusted_uuid_before_connecting(workspace):
    database = Database("postgresql://localhost/space_corp_test")
    database.session_factory = Mock()
    try:
        with pytest.raises(ValueError, match="workspace UUID"):
            with database.query_session(workspace):
                pytest.fail("Invalid context must not yield a session")
        database.session_factory.assert_not_called()
    finally:
        database.dispose()


@pytest.mark.parametrize("timeout", [0, -1, 60001, True, "100", 1.5, None])
def test_query_session_rejects_disabled_or_unbounded_timeout_before_connecting(timeout):
    database = Database("postgresql://localhost/space_corp_test")
    database.session_factory = Mock()
    try:
        with pytest.raises(ValueError, match="Statement timeout"):
            with database.query_session(uuid4(), statement_timeout_ms=timeout):
                pytest.fail("Invalid timeout must not yield a session")
        database.session_factory.assert_not_called()
    finally:
        database.dispose()


@pytest.fixture
def query_databases(migrated_database, integration_application_database_url):
    """Two real workspaces; the query connection uses the restricted login."""
    application = Database(integration_application_database_url)
    owner = Database(migrated_database)
    workspaces = [uuid4(), uuid4()]
    facilities = [uuid4(), uuid4()]
    try:
        with owner.session() as session:
            session.add_all([WorkspaceRecord(id=id_) for id_ in workspaces])
        with owner.session() as session:
            for workspace, facility in zip(workspaces, facilities, strict=True):
                session.add(
                    FacilityRecord(
                        id=facility,
                        workspace_id=workspace,
                        code="SAME-CODE",
                        name="Original",
                        facility_type="lunar_installation",
                        location="Moon",
                        operational_status="operational",
                    )
                )
        yield application, owner, workspaces, facilities
    finally:
        with owner.session() as session:
            session.execute(
                delete(FacilityRecord).where(FacilityRecord.workspace_id.in_(workspaces))
            )
            session.execute(delete(WorkspaceRecord).where(WorkspaceRecord.id.in_(workspaces)))
        application.dispose()
        owner.dispose()


def query_settings(session):
    return session.execute(
        text(
            "SELECT pg_backend_pid(), current_setting('transaction_read_only'), current_setting('statement_timeout'), current_setting('app.workspace_id', true), current_setting('transaction_isolation')"
        )
    ).one()


@pytest.mark.integration
def test_query_session_scopes_reads_and_resets_successful_pooled_connection(query_databases):
    application, _, workspaces, facilities = query_databases
    with application.session() as session:
        baseline = query_settings(session)
    pids = []
    for workspace, facility in zip(workspaces, facilities, strict=True):
        with application.query_session(workspace) as session:
            pid, read_only, timeout, scope, isolation = query_settings(session)
            pids.append(pid)
            assert (read_only, timeout, scope, isolation) == (
                "on",
                "5s",
                str(workspace),
                "repeatable read",
            )
            assert session.scalar(text("SELECT current_user")) == "space_corp_app"
            assert session.scalars(select(FacilityRecord.id)).all() == [facility]
            assert session.get(FacilityRecord, facilities[1 - facilities.index(facility)]) is None
    with application.session() as session:
        after = query_settings(session)
        assert after[:3] == baseline[:3]
        assert after[3] in (None, "")
        assert after[4] == baseline[4]
        assert session.scalars(select(FacilityRecord.id)).all() == []
    assert pids == [baseline[0], baseline[0]]
    # Ordinary operational writes retain their existing grants after query use.
    with application.workspace_session(workspaces[0]) as session:
        session.execute(
            update(FacilityRecord).where(FacilityRecord.id == facilities[0]).values(name="Allowed")
        )


@pytest.mark.integration
@pytest.mark.parametrize("write", ["insert", "update", "delete", "orm-flush", "orm-commit"])
def test_query_session_rejects_writes_and_recovers_connection(query_databases, write):
    from sqlalchemy.exc import DBAPIError

    application, owner, workspaces, facilities = query_databases
    with application.session() as session:
        before = query_settings(session)
    with pytest.raises(DBAPIError) as error:
        with application.query_session(workspaces[0]) as session:
            if write == "insert":
                session.execute(
                    text(
                        "INSERT INTO facilities (id, workspace_id, code, name, facility_type, location, operational_status) VALUES (:id, :workspace, 'NEW', 'New', 'lunar_installation', 'Moon', 'operational')"
                    ),
                    {"id": uuid4(), "workspace": workspaces[0]},
                )
            elif write == "update":
                session.execute(
                    update(FacilityRecord)
                    .where(FacilityRecord.id == facilities[0])
                    .values(name="Forbidden")
                )
            elif write == "delete":
                session.execute(delete(FacilityRecord).where(FacilityRecord.id == facilities[0]))
            else:
                session.get(FacilityRecord, facilities[0]).name = "Forbidden"
                if write == "orm-flush":
                    session.flush()
                # orm-commit exercises the context manager's implicit flush.
    assert error.value.orig.sqlstate == "25006"
    with application.session() as session:
        after = query_settings(session)
        assert after[:3] == before[:3]
        assert after[3] in (None, "")
        assert after[4] == before[4]
    with owner.session() as session:
        assert session.get(FacilityRecord, facilities[0]).name == "Original"
        assert (
            len(
                session.scalars(
                    select(FacilityRecord).where(FacilityRecord.workspace_id.in_(workspaces))
                ).all()
            )
            == 2
        )


@pytest.mark.integration
def test_query_session_timeout_rolls_back_and_connection_can_be_reused(query_databases):
    from sqlalchemy.exc import DBAPIError

    application, _, workspaces, facilities = query_databases
    with application.session() as session:
        before = query_settings(session)
    with pytest.raises(DBAPIError) as error:
        with application.query_session(workspaces[0], statement_timeout_ms=25) as session:
            session.execute(text("SELECT pg_sleep(1)"))
    assert error.value.orig.sqlstate == "57014"
    with application.session() as session:
        after = query_settings(session)
        assert after[:3] == before[:3]
        assert after[3] in (None, "")
    with application.query_session(workspaces[1]) as session:
        assert session.scalars(select(FacilityRecord.id)).all() == [facilities[1]]


@pytest.mark.integration
def test_query_session_python_exception_cleans_up_and_closed_session_cannot_autobegin(
    query_databases,
):
    from sqlalchemy.exc import InvalidRequestError

    application, _, workspaces, _ = query_databases
    with application.session() as session:
        before = query_settings(session)
    with pytest.raises(RuntimeError, match="caller failure"):
        with application.query_session(workspaces[0]) as query:
            raise RuntimeError("caller failure")
    with pytest.raises(InvalidRequestError, match="autobegin|Autobegin"):
        query.execute(text("SELECT 1"))
    with application.session() as session:
        after = query_settings(session)
        assert after[:3] == before[:3]
        assert after[3] in (None, "")


@pytest.mark.integration
def test_query_session_count_and_records_share_snapshot(query_databases):
    application, owner, workspaces, facilities = query_databases
    with application.query_session(workspaces[0]) as session:
        assert session.scalar(select(FacilityRecord.name)) == "Original"
        with owner.session() as writer:
            writer.execute(
                update(FacilityRecord)
                .where(FacilityRecord.id == facilities[0])
                .values(name="Changed")
            )
        assert session.scalar(select(FacilityRecord.name)) == "Original"
    with application.query_session(workspaces[0]) as session:
        assert session.scalar(select(FacilityRecord.name)) == "Changed"


@pytest.mark.integration
@pytest.mark.parametrize("finish", ["commit", "rollback"])
def test_query_session_cannot_silently_restart_after_early_end(query_databases, finish):
    from sqlalchemy.exc import InvalidRequestError

    application, _, workspaces, _ = query_databases
    with application.query_session(workspaces[0]) as session:
        getattr(session, finish)()
        with pytest.raises(InvalidRequestError):
            session.execute(text("SELECT 1"))
    with pytest.raises(InvalidRequestError):
        session.execute(text("SELECT 1"))


@pytest.mark.integration
def test_query_session_setup_failure_does_not_yield_or_leak_settings(query_databases):
    from sqlalchemy import event

    application, _, workspaces, _ = query_databases
    with application.session() as session:
        before = query_settings(session)

    def fail_setup(connection, cursor, statement, parameters, context, executemany):
        if "set_config" in statement:
            raise RuntimeError("setup failed")

    event.listen(application.engine, "before_cursor_execute", fail_setup)
    try:
        with pytest.raises(RuntimeError, match="setup failed"):
            with application.query_session(workspaces[0]):
                pytest.fail("Failed setup must not expose the session")
    finally:
        event.remove(application.engine, "before_cursor_execute", fail_setup)
    with application.session() as session:
        after = query_settings(session)
        assert after[:3] == before[:3]
        assert after[3] in (None, "")
        assert after[4] == before[4]
