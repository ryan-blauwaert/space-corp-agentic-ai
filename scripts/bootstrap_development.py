"""Apply migrations and populate a selected local development workspace."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database import Database
from scripts.dataset_manifest import DEFAULT_MANIFEST, load_manifest
from scripts.dataset_queries import validate_scenarios
from scripts.seed_dataset import seed_workspace, validate_workspace
from scripts.seed_support import SeedConfigurationError

ROOT = Path(__file__).resolve().parents[1]


def bootstrap(settings: Settings, workspace: UUID | None = None, *, manifest_path: Path = DEFAULT_MANIFEST, refresh: bool = False, validate: bool = False) -> dict[str, object]:
    """Guards run before migrations, publication, or operational writes."""
    if settings.environment != "development" or settings.migration_database_url is None:
        raise SeedConfigurationError("A development migration-owner connection is required.")
    url = make_url(str(settings.migration_database_url))
    if not url.database or url.database.startswith("space_corp_test"):
        raise SeedConfigurationError("Development bootstrap cannot target a test database.")
    local_hosts = (None, "localhost", "127.0.0.1", "::1")
    query_hosts = url.normalized_query.get("host", ())
    if (url.host not in local_hosts or "service" in url.query
            or any(host not in local_hosts and not host.startswith("/") for host in query_hosts)):
        raise SeedConfigurationError("Development bootstrap requires local PostgreSQL.")
    workspace = workspace or settings.default_workspace_id
    if workspace is None:
        raise SeedConfigurationError("Supply --workspace or SPACE_CORP_DEFAULT_WORKSPACE_ID.")
    manifest = load_manifest(manifest_path)
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["migration_database_url"] = str(settings.migration_database_url)
    command.upgrade(config, "head")
    database = Database(str(settings.migration_database_url))
    try:
        with database.session() as session:
            counts = seed_workspace(session, workspace, manifest, refresh=refresh)
            scenarios = None
            if validate or refresh:
                validate_workspace(session, workspace, manifest)
                scenarios = validate_scenarios(session, workspace, manifest)
            return dict(workspace_id=str(workspace), baseline=manifest.version,
                        catalog=manifest.catalog.version, counts=counts, scenarios_verified=scenarios)
    finally:
        database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=UUID)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--refresh", action="store_true", help="Replace only this pinned workspace's operational records with the frozen baseline.")
    parser.add_argument("--validate", action="store_true", help="Verify exact baseline rows and Q1–Q5 evidence; edited copies will fail validation.")
    args = parser.parse_args()
    try:
        result = bootstrap(Settings(), args.workspace, manifest_path=args.manifest, refresh=args.refresh, validate=args.validate)
    except (SeedConfigurationError, ValueError) as error:
        parser.exit(1, f"Dataset bootstrap failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
