"""Shared catalog reads, revision-specific compatibility, and error contracts."""

from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import create_app
from scripts.dataset_manifest import shared_id
from tests.app.api.routes.conftest import ReadApiDataset


@pytest.mark.integration
def test_shared_catalog_and_compatibility(read_api_dataset: ReadApiDataset) -> None:
    data = read_api_dataset
    catalog = data.manifest.catalog
    release = str(shared_id(catalog.version, "release", catalog.version))
    for model in catalog.models:
        model_id = shared_id(catalog.version, "models", model.key)
        path = f"/equipment-models/{model_id}"
        response = data.client.get(path)
        assert response.status_code == 200
        assert response.json()["code"] == model.key
        assert response.json()["name"] == model.name
        assert response.json()["catalog_release_id"] == release
        assert "workspace_id" not in response.json()
        # Catalog definitions are shared even with an empty, unpinned workspace.
        assert data.other_client.get(path).json() == response.json()
        assert data.empty_client.get(path).json() == response.json()
        result = data.client.get(path + "/components").json()
        expected = sorted(component for key, component in catalog.compatibility if key == model.key)
        assert [item["code"] for item in result["items"]] == expected
        assert result["pagination"]["total"] == len(expected)
        assert all(item["catalog_release_id"] == release for item in result["items"])
        page = data.client.get(path + "/components?limit=1&offset=1").json()
        assert page["items"] == result["items"][1:2]
        assert page["pagination"]["total"] == len(expected)
        assert data.client.get(path + "/components?offset=100").json()["items"] == []
        for item in result["items"]:
            assert data.client.get(f"/components/{item['id']}").json() == item
    # Also verify components that have no compatibility association.
    for component in catalog.components:
        component_id = shared_id(catalog.version, "components", component.key)
        response = data.client.get(f"/components/{component_id}")
        assert response.status_code == 200
        assert response.json()["name"] == component.name
        assert response.json()["catalog_release_id"] == release
    for path in (f"/equipment-models/{uuid4()}", f"/components/{uuid4()}", f"/equipment-models/{uuid4()}/components"):
        response = data.client.get(path)
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize("path", [
    "/equipment-models/invalid", "/components/invalid", "/equipment-models/invalid/components",
    f"/equipment-models/{uuid4()}/components?limit=0",
    f"/equipment-models/{uuid4()}/components?offset=-1",
    f"/equipment-models/{uuid4()}/components?limit=101",
    f"/equipment-models/{uuid4()}/components?workspace_id=other",
])
def test_catalog_validation_does_not_query_database(path: str) -> None:
    database = MagicMock()
    app = create_app(Settings(_env_file=None, database_url=None, default_workspace_id=uuid4()), database)
    with TestClient(app) as client:
        assert client.get(path).status_code == 422
    database.session.assert_not_called()


@pytest.mark.parametrize("path", [f"/equipment-models/{uuid4()}", f"/components/{uuid4()}", f"/equipment-models/{uuid4()}/components"])
def test_catalog_database_failure(path: str) -> None:
    database = MagicMock()
    database.session.side_effect = OperationalError("SELECT private_data", {}, Exception("password=secret"))
    app = create_app(Settings(_env_file=None, database_url=None, default_workspace_id=uuid4()), database)
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert "secret" not in response.text
    assert "private_data" not in response.text


@pytest.mark.integration
@pytest.mark.parametrize("collection,entity", [("equipment-models", "models"), ("components", "components")])
def test_catalog_lists_releases_and_unused_records(
    read_api_dataset: ReadApiDataset, migrated_database: str,
    collection: str, entity: str,
) -> None:
    from sqlalchemy import delete
    from app.database import Database
    from app.equipment.models import CatalogReleaseRecord, EquipmentModelRecord, ComponentRecord

    data = read_api_dataset
    catalog = data.manifest.catalog
    release = str(shared_id(catalog.version, "release", catalog.version))
    definitions = getattr(catalog, entity)
    path = f"/{collection}"
    owner = Database(migrated_database)
    other_release, unused_id = uuid4(), uuid4()
    record = EquipmentModelRecord if entity == "models" else ComponentRecord
    try:
        with owner.session() as session:
            session.add(CatalogReleaseRecord(id=other_release, code=f"unused-{other_release}"))
            session.flush()
            session.add(record(id=unused_id, catalog_release_id=other_release,
                               code=definitions[0].key, name="Unused catalog revision"))
        response = data.client.get(path, params={"catalog_release_id": release, "limit": 100})
        assert response.status_code == 200
        page = response.json()
        assert page["pagination"] == {"limit": 100, "offset": 0, "total": len(definitions)}
        assert [item["code"] for item in page["items"]] == sorted(item.key for item in definitions)
        assert all(item["catalog_release_id"] == release for item in page["items"])
        assert {item["id"] for item in page["items"]} == {
            str(shared_id(catalog.version, entity, item.key)) for item in definitions
        }
        for item in page["items"]:
            assert data.client.get(path + "/" + item["id"]).json() == item
            assert "workspace_id" not in item
        for client in (data.other_client, data.empty_client):
            assert client.get(path, params={"catalog_release_id": release, "limit": 100}).json() == page
        result = data.client.get(path, params={"catalog_release_id": release, "limit": 2, "offset": 1}).json()
        assert result["items"] == page["items"][1:3]
        assert result["pagination"]["total"] == len(definitions)
        assert data.client.get(path, params={"catalog_release_id": release, "offset": 1000}).json()["items"] == []
        unknown = data.client.get(path, params={"catalog_release_id": str(uuid4())})
        assert unknown.status_code == 200
        assert unknown.json() == {"items": [], "pagination": {"limit": 50, "offset": 0, "total": 0}}
        unused = data.client.get(path, params={"catalog_release_id": str(other_release)}).json()
        assert unused["pagination"]["total"] == 1
        assert unused["items"][0]["id"] == str(unused_id)
        # Unfiltered browsing includes every release, with ID breaking equal-code ties.
        all_items = []
        while True:
            result = data.client.get(path, params={"limit": 100, "offset": len(all_items)}).json()
            all_items.extend(result["items"])
            if len(all_items) >= result["pagination"]["total"]:
                break
            assert result["items"]
        assert all_items == sorted(all_items, key=lambda item: (item["code"], item["id"]))
        assert {release, str(other_release)} <= {item["catalog_release_id"] for item in all_items}
        assert len(all_items) == result["pagination"]["total"]
        assert str(unused_id) in {item["id"] for item in all_items}
        assert data.client.post(path, json={}).status_code == 405
    finally:
        with owner.session() as session:
            session.execute(delete(record).where(record.catalog_release_id == other_release))
            session.execute(delete(CatalogReleaseRecord).where(CatalogReleaseRecord.id == other_release))
        owner.dispose()


@pytest.mark.parametrize("collection", ["equipment-models", "components"])
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "catalog_release_id=invalid", "workspace_id=other", "search=unsupported"])
def test_catalog_list_validation(collection: str, query: str) -> None:
    database = MagicMock()
    app = create_app(Settings(_env_file=None, database_url=None, default_workspace_id=uuid4()), database)
    with TestClient(app) as client:
        assert client.get(f"/{collection}?{query}").status_code == 422
    database.session.assert_not_called()


@pytest.mark.parametrize("path", ["/equipment-models", "/components"])
def test_catalog_list_database_failure(path: str) -> None:
    test_catalog_database_failure(path)
