from uuid import uuid4

import pytest
from sqlalchemy import delete, text

from app.database import Database
from app.equipment.models import CatalogReleaseRecord, ComponentRecord, EquipmentModelRecord
from app.workspaces.models import WorkspaceRecord
from scripts.dataset_manifest import load_manifest
from scripts.seed_dataset import OPERATIONAL, seed_workspace


@pytest.fixture
def query_data(migrated_database, integration_application_database_url):
    owner, app = Database(migrated_database), Database(integration_application_database_url)
    manifest = load_manifest()
    workspaces = [uuid4(), uuid4()]
    extra_release, extra_model, extra_component = uuid4(), uuid4(), uuid4()
    try:
        with owner.session() as session:
            session.execute(
                text(
                    "GRANT EXECUTE ON FUNCTION public.current_workspace_catalog_release() TO space_corp_app"
                )
            )
            for workspace in workspaces:
                seed_workspace(session, workspace, manifest)
            session.add(CatalogReleaseRecord(id=extra_release, code=str(extra_release)))
            session.flush()
            session.add(
                EquipmentModelRecord(
                    id=extra_model,
                    catalog_release_id=extra_release,
                    code="M01",
                    name="Other revision",
                )
            )
            session.add(
                ComponentRecord(
                    id=extra_component,
                    catalog_release_id=extra_release,
                    code="C01",
                    name="Other component revision",
                )
            )
        yield app, owner, manifest, workspaces, extra_model, extra_component
    finally:
        with owner.session() as session:
            for record in reversed(OPERATIONAL):
                session.execute(delete(record).where(record.workspace_id.in_(workspaces)))
            session.execute(delete(WorkspaceRecord).where(WorkspaceRecord.id.in_(workspaces)))
            session.execute(
                delete(EquipmentModelRecord).where(EquipmentModelRecord.id == extra_model)
            )
            session.execute(delete(ComponentRecord).where(ComponentRecord.id == extra_component))
            session.execute(
                delete(CatalogReleaseRecord).where(CatalogReleaseRecord.id == extra_release)
            )
        app.dispose()
        owner.dispose()
