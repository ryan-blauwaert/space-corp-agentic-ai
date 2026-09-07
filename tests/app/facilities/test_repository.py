from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.database import Database
from app.facilities.domain import FacilityOperationalStatus, FacilityType, NewFacility
from app.facilities.repository import SqlAlchemyFacilityRepository
from app.workspaces.models import WorkspaceRecord


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def integration_session(integration_database_url: str) -> Iterator[Session]:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    database = Database(integration_database_url)
    session = database.session_factory()
    transaction = session.begin()

    try:
        yield session
    finally:
        transaction.rollback()
        session.close()
        database.dispose()


@pytest.fixture
def workspace_id(integration_session: Session) -> UUID:
    workspace = WorkspaceRecord(id=uuid4())
    integration_session.add(workspace)
    integration_session.flush()

    return workspace.id


def make_new_facility(code: str = "LUN-OPS-01") -> NewFacility:
    return NewFacility(
        code=code,
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )


@pytest.mark.integration
def test_repository_creates_and_retrieves_facility(
    integration_session: Session,
    workspace_id: UUID,
) -> None:
    repository = SqlAlchemyFacilityRepository(integration_session)

    created = repository.create(workspace_id, make_new_facility())
    retrieved = repository.get_by_id(workspace_id, created.id)

    assert retrieved == created


@pytest.mark.integration
def test_repository_returns_none_for_missing_facility(
    integration_session: Session,
    workspace_id: UUID,
) -> None:
    repository = SqlAlchemyFacilityRepository(integration_session)

    assert repository.get_by_id(workspace_id, uuid4()) is None


@pytest.mark.integration
def test_repository_lists_facilities_in_code_order(
    integration_session: Session,
    workspace_id: UUID,
) -> None:
    repository = SqlAlchemyFacilityRepository(integration_session)
    repository.create(workspace_id, make_new_facility("ORB-OPS-02"))
    repository.create(workspace_id, make_new_facility("LUN-OPS-01"))

    facilities = repository.list_by_workspace(workspace_id)

    assert [facility.code for facility in facilities] == ["LUN-OPS-01", "ORB-OPS-02"]


@pytest.mark.integration
def test_repository_excludes_another_workspaces_facility(
    integration_session: Session,
    workspace_id: UUID,
) -> None:
    repository = SqlAlchemyFacilityRepository(integration_session)
    other_workspace_id = uuid4()
    integration_session.add(WorkspaceRecord(id=other_workspace_id))
    integration_session.flush()
    other_facility = repository.create(other_workspace_id, make_new_facility())

    assert repository.get_by_id(workspace_id, other_facility.id) is None
    assert repository.list_by_workspace(workspace_id) == []
