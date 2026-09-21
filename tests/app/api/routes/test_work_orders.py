"""Acceptance coverage for the work-orders read API."""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import create_app
from tests.app.api.routes.conftest import ReadApiDataset


@pytest.mark.integration
def test_work_orders_read_contract(read_api_dataset: ReadApiDataset) -> None:
    data = read_api_dataset
    client = data.client
    expected = data.rows["work_orders"]
    response = client.get("/work-orders?limit=100")
    assert response.status_code == 200
    items = response.json()["items"]
    assert response.json()["pagination"]["total"] == len(expected)
    # Inventory exceeds one page; fetch the remaining rows.
    if len(expected) > 100:
        items += client.get("/work-orders?limit=100&offset=100").json()["items"]
    assert len(items) == len(expected)
    assert {item["id"] for item in items} == {str(row["id"]) for row in expected}
    expected_by_id = {str(row["id"]): row for row in expected}
    for item in items:
        row = expected_by_id[item["id"]]
        assert set(item) == set(row) - {"workspace_id"}
        for key, value in item.items():
            target = row[key]
            if isinstance(target, datetime):
                assert datetime.fromisoformat(value) == target
            elif target is None or isinstance(target, (int, str)):
                assert value == target
            else:
                assert value == str(target)
    assert [item["id"] for item in items] == [str(row["id"]) for row in sorted(expected, key=lambda row: (row["reference_code"], row["id"]))]
    assert client.get(f"/work-orders/{items[0]['id']}").json() == items[0]
    page = client.get("/work-orders?limit=2&offset=1").json()
    assert page["items"] == items[1:3]
    assert page["pagination"] == {"limit": 2, "offset": 1, "total": len(expected)}
    assert client.get("/work-orders?offset=1000").json()["items"] == []
    assert data.empty_client.get("/work-orders").json()["pagination"]["total"] == 0
    assert data.empty_client.get("/work-orders").json()["items"] == []

    for field in ['facility_id', 'status', 'priority']:
        value = next(item[field] for item in items if item[field] is not None)
        matches = [item for item in items if item[field] == value]
        result = client.get("/work-orders", params={field: value, "limit": 100})
        assert result.status_code == 200
        assert result.json()["items"] == matches[:100]
        assert result.json()["pagination"]["total"] == len(matches)
    combined = {field: items[0][field] for field in ['facility_id', 'status', 'priority'] if items[0][field] is not None}
    matches = [item for item in items if all(item[key] == value for key, value in combined.items())]
    result = client.get("/work-orders", params={**combined, "limit": 1}).json()
    assert result["items"] == matches[:1]
    assert result["pagination"]["total"] == len(matches)

    other_item = data.other_client.get("/work-orders").json()["items"][0]
    for record_id in (other_item["id"], str(uuid4())):
        response = client.get(f"/work-orders/{record_id}", headers={"X-Workspace-ID": str(data.other_id)})
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["status"] == 404
    for facility in (other_item["facility_id"], str(uuid4())):
        result = client.get("/work-orders", params={"facility_id": facility}).json()
        assert result["items"] == []
        assert result["pagination"]["total"] == 0
    assert client.get("/work-orders", params={"workspace_id": str(data.other_id)}).status_code == 422
    assert client.get("/work-orders", headers={"X-Workspace-ID": str(data.other_id)}).json()["items"] == items[:50]
    assert client.post("/work-orders", json={}).status_code == 405
    assert client.patch(f"/work-orders/{items[0]['id']}", json={}).status_code == 405


@pytest.mark.parametrize("suffix", ["/not-a-uuid", "?limit=0", "?limit=101", "?offset=-1", "?facility_id=invalid", "?workspace_id=other", '?status=unknown', '?priority=unknown'])
def test_work_orders_invalid_requests_do_not_query_database(suffix: str) -> None:
    database = MagicMock()
    app = create_app(Settings(_env_file=None, database_url=None, default_workspace_id=uuid4()), database)
    with TestClient(app) as client:
        response = client.get("/work-orders" + suffix)
    assert response.status_code == 422
    database.workspace_session.assert_not_called()


@pytest.mark.parametrize("suffix", ["", f"/{uuid4()}"])
def test_work_orders_database_failure(suffix: str) -> None:
    database = MagicMock()
    database.workspace_session.side_effect = OperationalError("SELECT private_data", {}, Exception("password=secret"))
    app = create_app(Settings(_env_file=None, database_url=None, default_workspace_id=uuid4()), database)
    with TestClient(app) as client:
        response = client.get("/work-orders" + suffix)
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert "secret" not in response.text
    assert "private_data" not in response.text
