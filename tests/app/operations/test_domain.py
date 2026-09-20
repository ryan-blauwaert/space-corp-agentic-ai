from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.operations.domain import (
    INCIDENT_FAULT_CODE_MAX_LENGTH,
    INCIDENT_REFERENCE_CODE_MAX_LENGTH,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    NewIncident,
)


def test_incident_normalizes_fault_code_and_accepts_valid_lifecycle() -> None:
    occurred_at = datetime.now(UTC)
    incident = NewIncident(
        facility_id=uuid4(),
        equipment_unit_id=uuid4(),
        reference_code="INC-ECS-001",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        occurred_at=occurred_at,
        fault_code=" airflow_low ",
    )

    assert incident.fault_code == "AIRFLOW_LOW"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"reference_code": ""}, "must not be blank"),
        ({"reference_code": "x" * (INCIDENT_REFERENCE_CODE_MAX_LENGTH + 1)}, "at most"),
        ({"fault_code": "x" * (INCIDENT_FAULT_CODE_MAX_LENGTH + 1)}, "at most"),
        ({"status": IncidentStatus.RESOLVED}, "must include a resolution time"),
        ({"resolved_at": datetime.now(UTC)}, "may include a resolution time"),
        ({"occurred_at": datetime.now()}, "timezone-aware"),
    ],
)
def test_new_incident_rejects_invalid_data(
    overrides: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "facility_id": uuid4(),
        "equipment_unit_id": uuid4(),
        "reference_code": "INC-ECS-001",
        "severity": IncidentSeverity.HIGH,
        "status": IncidentStatus.OPEN,
        "occurred_at": datetime.now(UTC),
        "fault_code": "AIRFLOW_LOW",
        "resolved_at": None,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        NewIncident(**values)  # type: ignore[arg-type]


def test_incident_requires_normalized_persisted_fault_code() -> None:
    with pytest.raises(ValueError, match="trimmed and uppercase"):
        Incident(
            id=uuid4(), workspace_id=uuid4(), facility_id=uuid4(), equipment_unit_id=None,
            reference_code="INC-LUN-001", severity=IncidentSeverity.LOW,
            status=IncidentStatus.OPEN, occurred_at=datetime.now(UTC),
            fault_code="airflow_low", resolved_at=None,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
