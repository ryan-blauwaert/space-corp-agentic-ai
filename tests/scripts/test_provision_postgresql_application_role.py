"""Exercise provisioning against a disposable cluster, never a developer database."""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


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
            check=True, capture_output=True, env=environment,
        )
        subprocess.run(
            [str(binaries / "pg_ctl"), "-D", str(data), "-l", str(root / "server.log"),
             "-o", f"-k {directory} -h '' -p 55439", "-w", "start"],
            check=True, capture_output=True, env=environment,
        )
        try:
            psql = binaries / "psql"
            for sql in (
                "CREATE ROLE space_corp LOGIN",
                "CREATE DATABASE space_corp OWNER space_corp",
                "CREATE DATABASE space_corp_test OWNER space_corp",
            ):
                subprocess.run([str(psql), "-X", "-d", "postgres", "-c", sql],
                               env=environment, check=True, capture_output=True)
            for name in ("space_corp", "space_corp_test"):
                migration_environment = dict(
                    environment,
                    SPACE_CORP_MIGRATION_DATABASE_URL=(
                        f"postgresql+psycopg://space_corp@localhost/{name}?host={directory}&port=55439"
                    ),
                )
                subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                               cwd=ROOT, env=migration_environment, check=True, capture_output=True)
            yield psql, environment
        finally:
            subprocess.run([str(binaries / "pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop"],
                           env=environment, check=True, capture_output=True)


def sql(cluster: tuple[Path, dict[str, str]], statement: str) -> str:
    psql, environment = cluster
    return subprocess.run([str(psql), "-X", "-At", "-v", "ON_ERROR_STOP=1", "-d", "space_corp", "-c", statement],
                          env=environment, check=True, capture_output=True, text=True).stdout.strip()


def provision(cluster: tuple[Path, dict[str, str]]) -> subprocess.CompletedProcess[str]:
    psql, environment = cluster
    return subprocess.run(
        [str(psql), "-X", "-d", "postgres", "-f", str(ROOT / "scripts/provision_postgresql_application_role.sql")],
        env=environment, capture_output=True, text=True,
    )


def test_provisioning_removes_legacy_grants_and_is_repeatable(
    provisioning_cluster: tuple[Path, dict[str, str]],
) -> None:
    assert provision(provisioning_cluster).returncode == 0
    sql(provisioning_cluster, "GRANT ALL ON ALL TABLES IN SCHEMA public TO space_corp_app")
    sql(provisioning_cluster, "ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public GRANT ALL ON TABLES TO space_corp_app")
    assert provision(provisioning_cluster).returncode == 0
    assert provision(provisioning_cluster).returncode == 0
    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        assert sql(
            provisioning_cluster,
            f"SELECT has_table_privilege('space_corp_app', 'facilities', '{privilege}')",
        ) == "t"
    assert sql(provisioning_cluster, "SELECT has_table_privilege('space_corp_app', 'alembic_version', 'SELECT,INSERT,UPDATE,DELETE')") == "f"
    assert sql(provisioning_cluster, "SELECT has_table_privilege('space_corp_app', 'workspaces', 'SELECT,INSERT,UPDATE,DELETE')") == "f"
    sql(provisioning_cluster, "SET ROLE space_corp; CREATE TABLE future_table (id integer)")
    assert sql(provisioning_cluster, "SELECT has_table_privilege('space_corp_app', 'future_table', 'SELECT,INSERT,UPDATE,DELETE')") == "f"


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
        sql(provisioning_cluster, "DROP TABLE facilities")
    result = provision(provisioning_cluster)
    assert result.returncode == 3
    assert "ERROR" in result.stderr
    # Inspect direct grants: the deliberately unsafe membership already inherits access.
    assert sql(provisioning_cluster,
               "SELECT count(*) FROM information_schema.role_table_grants "
               "WHERE grantee = 'space_corp_app' AND table_schema = 'public'") == "0"
