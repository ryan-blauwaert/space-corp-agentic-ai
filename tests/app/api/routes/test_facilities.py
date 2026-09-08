from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

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
def api_workspaces(integration_migration_database_url: str) -> Iterator[ApiWorkspaces]:
    database = Database(integration_migration_database_url)
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
    assert response.json() == {"detail": "The Facility API database is not configured."}


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
def test_list_facilities_uses_the_server_configured_workspace_only(
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

        assert response.status_code == 200
        assert [facility["code"] for facility in response.json()["items"]] == [
            "LUN-OPS-01",
            "ORB-OPS-01",
        ]
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
