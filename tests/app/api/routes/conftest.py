"""Two independent baseline copies served through the restricted application role."""

from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.baselines.models import BaselineRecord
from app.config import Settings
from app.database import Database
from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    equipment_model_components,
)
from app.main import create_app
from app.workspaces.models import WorkspaceRecord
from scripts.dataset_manifest import Manifest, load_manifest, shared_id
from scripts.seed_dataset import OPERATIONAL, baseline_rows, seed_workspace


@dataclass
class ReadApiDataset:
    client: TestClient
    other_client: TestClient
    empty_client: TestClient
    workspace_id: UUID
    other_id: UUID
    manifest: Manifest
    rows: dict[str, list[dict[str, object]]]


@pytest.fixture
def read_api_dataset(
    migrated_database: str, integration_application_database_url: str
) -> Iterator[ReadApiDataset]:
    owner = Database(migrated_database)
    database = Database(integration_application_database_url)
    first, other, empty = uuid4(), uuid4(), uuid4()
    document = load_manifest().model_dump(mode="json")
    document["version"] = f"api-{first}"
    document["catalog"]["version"] = f"api-catalog-{first}"
    manifest = Manifest.model_validate(document)
    release = shared_id(manifest.catalog.version, "release", manifest.catalog.version)

    def client(workspace: UUID) -> TestClient:
        return TestClient(
            create_app(
                Settings(
                    _env_file=None,
                    database_url=integration_application_database_url,
                    default_workspace_id=workspace,
                ),
                database,
            )
        )

    try:
        with owner.session() as session:
            seed_workspace(session, first, manifest)
            seed_workspace(session, other, manifest)
            session.add(WorkspaceRecord(id=empty))
        with client(first) as primary, client(other) as secondary, client(empty) as vacant:
            yield ReadApiDataset(
                primary,
                secondary,
                vacant,
                first,
                other,
                manifest,
                {record.__tablename__: rows for record, rows in baseline_rows(manifest, first)},
            )
    finally:
        with owner.session() as session:
            for record in reversed(OPERATIONAL):
                session.execute(
                    delete(record).where(record.workspace_id.in_([first, other, empty]))
                )
            session.execute(
                delete(WorkspaceRecord).where(WorkspaceRecord.id.in_([first, other, empty]))
            )
            session.execute(
                delete(BaselineRecord).where(BaselineRecord.catalog_release_id == release)
            )
            session.execute(
                delete(equipment_model_components).where(
                    equipment_model_components.c.catalog_release_id == release
                )
            )
            session.execute(
                delete(EquipmentModelRecord).where(
                    EquipmentModelRecord.catalog_release_id == release
                )
            )
            session.execute(
                delete(ComponentRecord).where(ComponentRecord.catalog_release_id == release)
            )
            session.execute(delete(CatalogReleaseRecord).where(CatalogReleaseRecord.id == release))
        database.dispose()
        owner.dispose()
