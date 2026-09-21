"""Incident query validation follows the domain's classification and time rules."""

import pytest
from pydantic import ValidationError

from app.schemas.operations import IncidentQuery


@pytest.mark.parametrize("values", [
    {"occurred_from": "2026-01-01T00:00:00"},
    {"occurred_before": "2026-01-01T00:00:00"},
    {"occurred_from": "2026-01-02T00:00:00Z", "occurred_before": "2026-01-01T00:00:00Z"},
    {"occurred_from": "2026-01-01T00:00:00Z", "occurred_before": "2026-01-01T00:00:00Z"},
    {"fault_code": " "}, {"fault_code": "x" * 65}, {"status": "unknown"},
])
def test_invalid_incident_queries(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        IncidentQuery.model_validate(values)


def test_incident_query_normalizes_fault_and_accepts_aware_window() -> None:
    query = IncidentQuery(fault_code=" pump fault ", occurred_from="2026-01-01T00:00:00Z", occurred_before="2026-02-01T00:00:00Z")
    assert query.fault_code == "PUMP FAULT"
    assert query.occurred_from < query.occurred_before
