from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.facilities.domain import (
    Facility,
    FacilityOperationalStatus,
    FacilityType,
)


def make_facility() -> Facility:
    timestamp = datetime(2026, 9, 7, tzinfo=UTC)

    return Facility(
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


def test_facility_retains_workspace_owned_operational_data() -> None:
    facility = make_facility()

    assert facility.code == "LUN-OPS-01"
    assert facility.facility_type is FacilityType.LUNAR_INSTALLATION
    assert facility.operational_status is FacilityOperationalStatus.OPERATIONAL


@pytest.mark.parametrize("field_name", ["code", "name", "location"])
def test_facility_rejects_blank_required_text(field_name: str) -> None:
    facility = make_facility()

    with pytest.raises(ValueError, match=field_name):
        replace(facility, **{field_name: "   "})
