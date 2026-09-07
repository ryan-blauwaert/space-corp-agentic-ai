from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.facilities.domain import (
    Facility,
    FACILITY_CODE_MAX_LENGTH,
    FACILITY_LOCATION_MAX_LENGTH,
    FACILITY_NAME_MAX_LENGTH,
    FacilityOperationalStatus,
    FacilityType,
    NewFacility,
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


def test_new_facility_contains_validated_creation_data() -> None:
    facility = NewFacility(
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )

    assert facility.code == "LUN-OPS-01"


def test_facility_is_immutable() -> None:
    facility = make_facility()

    with pytest.raises(FrozenInstanceError):
        facility.code = "LUN-OPS-02"  # type: ignore[misc]


@pytest.mark.parametrize("field_name", ["code", "name", "location"])
def test_facility_rejects_blank_required_text(field_name: str) -> None:
    facility = make_facility()

    with pytest.raises(ValueError, match=field_name):
        replace(facility, **{field_name: "   "})


@pytest.mark.parametrize("field_name", ["code", "name", "location"])
def test_new_facility_rejects_blank_required_text(field_name: str) -> None:
    facility = NewFacility(
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )

    with pytest.raises(ValueError, match=field_name):
        replace(facility, **{field_name: "   "})


@pytest.mark.parametrize(
    ("field_name", "maximum_length"),
    [
        ("code", FACILITY_CODE_MAX_LENGTH),
        ("name", FACILITY_NAME_MAX_LENGTH),
        ("location", FACILITY_LOCATION_MAX_LENGTH),
    ],
)
def test_new_facility_accepts_text_at_persistence_limit(
    field_name: str,
    maximum_length: int,
) -> None:
    facility = NewFacility(
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )

    updated_facility = replace(facility, **{field_name: "x" * maximum_length})

    assert getattr(updated_facility, field_name) == "x" * maximum_length


@pytest.mark.parametrize(
    ("field_name", "maximum_length"),
    [
        ("code", FACILITY_CODE_MAX_LENGTH),
        ("name", FACILITY_NAME_MAX_LENGTH),
        ("location", FACILITY_LOCATION_MAX_LENGTH),
    ],
)
def test_new_facility_rejects_text_over_persistence_limit(
    field_name: str,
    maximum_length: int,
) -> None:
    facility = NewFacility(
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )

    with pytest.raises(ValueError, match=field_name):
        replace(facility, **{field_name: "x" * (maximum_length + 1)})


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("facility_type", "lunar_installation"),
        ("operational_status", "operational"),
    ],
)
def test_new_facility_rejects_invalid_enum_types(
    field_name: str,
    invalid_value: str,
) -> None:
    facility = NewFacility(
        code="LUN-OPS-01",
        name="Lunar Operations One",
        facility_type=FacilityType.LUNAR_INSTALLATION,
        location="Mare Imbrium",
        operational_status=FacilityOperationalStatus.OPERATIONAL,
    )

    with pytest.raises(ValueError, match=field_name):
        replace(facility, **{field_name: invalid_value})
