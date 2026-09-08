from datetime import UTC, datetime
from uuid import uuid4

from app.facilities.domain import Facility, FacilityOperationalStatus, FacilityType
from app.facilities.models import FacilityRecord
from app.schemas.facilities import (
    FacilityListResponse,
    FacilityResponse,
)
from app.schemas.pagination import PaginationMetadata
from app.workspaces.models import WorkspaceRecord


def test_facility_response_serializes_public_facility_fields() -> None:
    timestamp = datetime(2026, 9, 7, tzinfo=UTC)
    facility = Facility(
        id=uuid4(),
        workspace_id=uuid4(),
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = FacilityResponse.model_validate(facility)

    assert response.id == facility.id
    assert response.code == "LUN-OPS-01"
    assert response.facility_type is FacilityType.LUNAR_INSTALLATION
    assert response.operational_status is FacilityOperationalStatus.OPERATIONAL
    assert "workspace_id" not in response.model_dump()


def test_facility_response_serializes_enums_as_stable_json_values() -> None:
    timestamp = datetime(2026, 9, 7, tzinfo=UTC)
    response = FacilityResponse(
        id=uuid4(),
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
        created_at=timestamp,
        updated_at=timestamp,
    )

    payload = response.model_dump(mode="json")

    assert payload["facility_type"] == "lunar_installation"
    assert payload["operational_status"] == "operational"


def test_facility_response_hydrates_from_a_sqlalchemy_record() -> None:
    timestamp = datetime(2026, 9, 7, tzinfo=UTC)
    workspace = WorkspaceRecord(id=uuid4(), created_at=timestamp)
    record = FacilityRecord(
        id=uuid4(),
        workspace=workspace,
        code="ORB-OPS-01",
        name="Orbital Operations One",
        facility_type="orbital_station",
        location="Low Earth Orbit",
        operational_status="degraded",
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = FacilityResponse.model_validate(record)

    assert response.facility_type is FacilityType.ORBITAL_STATION
    assert response.operational_status is FacilityOperationalStatus.DEGRADED


def test_facility_list_response_includes_pagination_metadata() -> None:
    response = FacilityListResponse(
        items=[],
        pagination=PaginationMetadata(limit=50, offset=0, total=0),
    )

    assert response.model_dump() == {
        "items": [],
        "pagination": {"limit": 50, "offset": 0, "total": 0},
    }


def test_facility_list_response_preserves_multiple_items_in_order() -> None:
    timestamp = datetime(2026, 9, 7, tzinfo=UTC)
    response = FacilityListResponse(
        items=[
            FacilityResponse(
                id=uuid4(),
                code="LUN-OPS-01",
                name="Lunar Operations One",
                facility_type=FacilityType.LUNAR_INSTALLATION,
                location="Mare Imbrium",
                operational_status=FacilityOperationalStatus.OPERATIONAL,
                created_at=timestamp,
                updated_at=timestamp,
            ),
            FacilityResponse(
                id=uuid4(),
                code="ORB-OPS-01",
                name="Orbital Operations One",
                facility_type=FacilityType.ORBITAL_STATION,
                location="Low Earth Orbit",
                operational_status=FacilityOperationalStatus.DEGRADED,
                created_at=timestamp,
                updated_at=timestamp,
            ),
        ],
        pagination=PaginationMetadata(limit=50, offset=0, total=2),
    )

    assert [facility.code for facility in response.items] == [
        "LUN-OPS-01",
        "ORB-OPS-01",
    ]
