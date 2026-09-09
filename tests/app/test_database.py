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

        assert revision == "0005_catalog_equipment_units"
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
def test_catalog_and_equipment_migration_downgrades_and_reapplies(
    integration_migration_database_url: str,
) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0004_facility_required_text")
        engine = create_database_engine(integration_migration_database_url)

        try:
            with engine.connect() as connection:
                catalog_release_table, equipment_model_table, equipment_unit_table = connection.execute(
                    text(
                        "SELECT to_regclass('public.catalog_releases'), "
                        "to_regclass('public.equipment_models'), "
                        "to_regclass('public.equipment_units')"
                    )
                ).one()

            assert catalog_release_table is None
            assert equipment_model_table is None
            assert equipment_unit_table is None
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
                        "'equipment_models', 'equipment_units'"
                        ")"
                    )
                ).scalars()
            )

        assert table_names == {
            "workspaces",
            "facilities",
            "catalog_releases",
            "equipment_models",
            "equipment_units",
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
                        "'equipment_models', 'equipment_units'"
                        ")"
                    )
                ).all()
            )
            role_memberships = session.execute(
                text(
                    "SELECT granted_role.rolname "
                    "FROM pg_auth_members AS membership "
                    "JOIN pg_roles AS member ON member.oid = membership.member "
                    "JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid "
                    "WHERE member.rolname = 'space_corp_app'"
                )
            ).scalars().all()

        assert (bypass_rls, is_superuser, can_create_role, can_create_database) == (
            False,
            False,
            False,
            False,
        )
        assert table_owners == {
            "catalog_releases": "space_corp",
            "equipment_models": "space_corp",
            "equipment_units": "space_corp",
            "facilities": "space_corp",
            "workspaces": "space_corp",
        }
        assert role_memberships == []

        connection_ids: list[int] = []
        with application_database.workspace_session(first_workspace_id) as session:
            assert session.execute(text("SELECT current_user")).scalar_one() == (
                "space_corp_app"
            )
            connection_ids.append(
                session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            first_facility = SqlAlchemyFacilityRepository(session).create(
                first_workspace_id, make_new_facility("LUN-OPS-01")
            )

        with application_database.workspace_session(second_workspace_id) as session:
            connection_ids.append(
                session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            second_facility = SqlAlchemyFacilityRepository(session).create(
                second_workspace_id, make_new_facility("ORB-OPS-01")
            )

        assert connection_ids[0] == connection_ids[1]

        with application_database.workspace_session(first_workspace_id) as session:
            assert session.get(FacilityRecord, second_facility.id) is None
            assert session.execute(
                update(FacilityRecord)
                .where(FacilityRecord.id == second_facility.id)
                .values(name="Should not update")
            ).rowcount == 0
            assert session.execute(select(FacilityRecord.id)).scalars().all() == [
                first_facility.id
            ]

        with pytest.raises(ProgrammingError):
            with application_database.workspace_session(first_workspace_id) as session:
                SqlAlchemyFacilityRepository(session).create(
                    second_workspace_id, make_new_facility("ORB-OPS-02")
                )

        with application_database.session() as session:
            final_connection_id = session.execute(
                text("SELECT pg_backend_pid()")
            ).scalar_one()
            assert session.execute(select(FacilityRecord.id)).scalars().all() == []
            assert session.execute(
                text("SELECT current_setting('app.workspace_id', true)")
            ).scalar_one() in (None, "")

        assert final_connection_id == connection_ids[0]
    finally:
        with migration_database.session() as session:
            session.execute(
                delete(FacilityRecord).where(
                    FacilityRecord.workspace_id.in_(
                        [first_workspace_id, second_workspace_id]
                    )
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
            session.add(WorkspaceRecord(id=workspace_id))
            session.flush()
            session.add(FacilityRecord(
                id=facility_id, workspace_id=workspace_id, code=" ", name="Legacy",
                facility_type="orbital_station", location="Orbit",
                operational_status="operational",
            ))
        with pytest.raises(IntegrityError):
            command.upgrade(config, "head")
        with database.session() as session:
            assert session.get(FacilityRecord, facility_id).code == " "
            assert session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003_facility_workspace_rls"
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
