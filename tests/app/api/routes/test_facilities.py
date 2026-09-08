from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import Database
from app.facilities.domain import FacilityOperationalStatus, FacilityType, NewFacility
from app.facilities.models import FacilityRecord
from app.facilities.repository import SqlAlchemyFacilityRepository
from app.main import create_app
from app.workspaces.models import WorkspaceRecord


@dataclass(frozen=True, slots=True)
class ApiWorkspaces:
    default_id: UUID
    empty_id: UUID
    other_id: UUID


def make_new_facility(code: str) -> NewFacility:
    return NewFacility(
        code=code,
        name=f"Facility {code}",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )


@pytest.fixture
def api_workspaces(migrated_database: str) -> Iterator[ApiWorkspaces]:
    database = Database(migrated_database)
    workspaces = ApiWorkspaces(default_id=uuid4(), empty_id=uuid4(), other_id=uuid4())

    try:
        with database.session() as session:
            session.add_all(
                [
                    WorkspaceRecord(id=workspaces.default_id),
                    WorkspaceRecord(id=workspaces.empty_id),
                    WorkspaceRecord(id=workspaces.other_id),
                ]
            )
            repository = SqlAlchemyFacilityRepository(session)
            repository.create(workspaces.default_id, make_new_facility("ORB-OPS-01"))
            repository.create(workspaces.default_id, make_new_facility("LUN-OPS-01"))
            repository.create(workspaces.other_id, make_new_facility("SEC-OPS-01"))

        yield workspaces
    finally:
        with database.session() as session:
            session.execute(
                delete(FacilityRecord).where(
                    FacilityRecord.workspace_id.in_(
                        [
                            workspaces.default_id,
                            workspaces.empty_id,
                            workspaces.other_id,
                        ]
                    )
                )
            )
            session.execute(
                delete(WorkspaceRecord).where(
                    WorkspaceRecord.id.in_(
                        [
                            workspaces.default_id,
                            workspaces.empty_id,
                            workspaces.other_id,
                        ]
                    )
                )
            )
        database.dispose()


def create_facility_application(
    database_url: str,
    workspace_id: UUID,
) -> tuple[FastAPI, Database]:
    database = Database(database_url)
    application = create_app(
        Settings(database_url=database_url, default_workspace_id=workspace_id),
        database,
    )

    return application, database


def test_list_facilities_returns_service_unavailable_without_a_database() -> None:
    application = create_app(Settings(database_url=None, default_workspace_id=uuid4()))

    with TestClient(application) as client:
        response = client.get("/facilities")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Service Unavailable",
        "status": 503,
        "detail": "The Facility API database is not configured.",
        "instance": "/facilities",
    }


@pytest.mark.integration
def test_list_facilities_returns_the_configured_workspaces_page(
    api_workspaces: ApiWorkspaces,
    integration_application_database_url: str,
) -> None:
    application, database = create_facility_application(
        integration_application_database_url,
        api_workspaces.default_id,
    )

    try:
        with TestClient(application) as client:
            response = client.get("/facilities")

        assert response.status_code == 200
        assert [facility["code"] for facility in response.json()["items"]] == [
            "LUN-OPS-01",
            "ORB-OPS-01",
        ]
        assert response.json()["pagination"] == {"limit": 50, "offset": 0, "total": 2}
    finally:
        database.dispose()


@pytest.mark.integration
def test_list_facilities_applies_pagination_limits_and_offsets(
    api_workspaces: ApiWorkspaces,
    integration_application_database_url: str,
) -> None:
    application, database = create_facility_application(
        integration_application_database_url,
        api_workspaces.default_id,
    )

    try:
        with TestClient(application) as client:
            response = client.get("/facilities?limit=1&offset=1")

        assert response.status_code == 200
        assert [facility["code"] for facility in response.json()["items"]] == [
            "ORB-OPS-01"
        ]
        assert response.json()["pagination"] == {"limit": 1, "offset": 1, "total": 2}
    finally:
        database.dispose()


@pytest.mark.integration
def test_list_facilities_returns_an_empty_page_for_an_empty_workspace(
    api_workspaces: ApiWorkspaces,
    integration_application_database_url: str,
) -> None:
    application, database = create_facility_application(
        integration_application_database_url,
        api_workspaces.empty_id,
    )

    try:
        with TestClient(application) as client:
            response = client.get("/facilities")

        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "pagination": {"limit": 50, "offset": 0, "total": 0},
        }
    finally:
        database.dispose()


@pytest.mark.integration
def test_list_facilities_rejects_a_client_supplied_workspace(
    api_workspaces: ApiWorkspaces,
    integration_application_database_url: str,
) -> None:
    application, database = create_facility_application(
        integration_application_database_url,
        api_workspaces.default_id,
    )

    try:
        with TestClient(application) as client:
            response = client.get(
                f"/facilities?workspace_id={api_workspaces.other_id}"
            )

        assert response.status_code == 422
    finally:
        database.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_facilities_rejects_invalid_pagination(
    api_workspaces: ApiWorkspaces,
    integration_application_database_url: str,
    query: str,
) -> None:
    application, database = create_facility_application(
        integration_application_database_url,
        api_workspaces.default_id,
    )

    try:
        with TestClient(application) as client:
            response = client.get(f"/facilities?{query}")

        assert response.status_code == 422
    finally:
        database.dispose()


@pytest.mark.integration
def test_get_facility_returns_only_a_record_in_the_configured_workspace(
    api_workspaces: ApiWorkspaces,
    integration_application_database_url: str,
) -> None:
    application, database = create_facility_application(
        integration_application_database_url, api_workspaces.default_id
    )
    try:
        with database.workspace_session(api_workspaces.other_id) as session:
            other_id = SqlAlchemyFacilityRepository(session).list_by_workspace(
                api_workspaces.other_id
            )[0].id
        with TestClient(application) as client:
            item = client.get("/facilities").json()["items"][0]
            response = client.get(f"/facilities/{item['id']}")
            assert response.status_code == 200
            assert response.json() == item
            assert "workspace_id" not in response.json()
            for facility_id in (other_id, uuid4()):
                response = client.get(
                    f"/facilities/{facility_id}?workspace_id={api_workspaces.other_id}",
                    headers={"X-Workspace-ID": str(api_workspaces.other_id)},
                )
                assert response.status_code == 404
                assert response.headers["content-type"] == "application/problem+json"
                assert response.json()["detail"] == "The requested Facility is not available."
                assert response.json()["status"] == 404
    finally:
        database.dispose()


@pytest.mark.parametrize("path", ["/facilities", "/facilities/not-a-uuid"])
def test_facility_routes_require_workspace_configuration(path: str) -> None:
    database = Mock(spec=Database)
    application = create_app(Settings(database_url=None, default_workspace_id=None), database)
    with TestClient(application) as client:
        response = client.get(path)
    assert response.status_code == 503
    assert response.json()["detail"] == "SPACE_CORP_DEFAULT_WORKSPACE_ID must be configured."
    database.workspace_session.assert_not_called()


@pytest.mark.parametrize("path", [
    "/facilities/not-a-uuid", "/facilities?limit=0", "/facilities?limit=101",
    "/facilities?offset=-1", "/facilities?limit=abc", "/facilities?workspace_id=other",
])
def test_invalid_facility_requests_do_not_access_database(path: str) -> None:
    database = Mock(spec=Database)
    application = create_app(Settings(database_url=None, default_workspace_id=uuid4()), database)
    with TestClient(application) as client:
        response = client.get(path)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    database.workspace_session.assert_not_called()


@pytest.mark.parametrize("path", ["/facilities", f"/facilities/{uuid4()}"])
def test_database_failure_returns_safe_problem_response(path: str) -> None:
    database = Mock(spec=Database)
    database.workspace_session.side_effect = OperationalError(
        "SELECT private_data", {}, Exception("password=secret")
    )
    application = create_app(Settings(database_url=None, default_workspace_id=uuid4()), database)
    with TestClient(application) as client:
        response = client.get(path)
    assert response.status_code == 503
    assert response.json()["detail"] == "The Facility API database is unavailable."
    assert "secret" not in response.text
    assert "private_data" not in response.text


def test_facility_openapi_contract() -> None:
    schema = create_app(Settings(database_url=None)).openapi()
    for path, operation_id in (
        ("/facilities", "listFacilities"),
        ("/facilities/{facility_id}", "getFacility"),
    ):
        operation = schema["paths"][path]["get"]
        assert operation["operationId"] == operation_id
        responses = operation["responses"]
        assert "application/json" in responses["200"]["content"]
        assert "application/json" in responses["422"]["content"]
        problem_statuses = ["503"] if path == "/facilities" else ["404", "503"]
        for status_code in problem_statuses:
            content = responses[status_code]["content"]
            assert set(content) == {"application/problem+json"}
            assert set(content["application/problem+json"]["schema"]["required"]) == {
                "title", "status", "detail"
            }
    parameters = {p["name"]: p["schema"] for p in schema["paths"]["/facilities"]["get"]["parameters"]}
    assert parameters["limit"]["minimum"] == 1
    assert parameters["limit"]["maximum"] == 100
    assert parameters["limit"]["default"] == 50
    assert parameters["offset"]["minimum"] == 0
    assert parameters["offset"]["default"] == 0
