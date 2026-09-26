from uuid import uuid4

import pytest
from sqlalchemy import select

from app.equipment.models import ComponentRecord, EquipmentModelRecord, EquipmentUnitRecord
from app.facilities.models import FacilityRecord
from app.operations.models import IncidentRecord, WorkOrderRecord
from app.queries.contracts import QueryContext, QueryPageRequest
from app.queries.equipment import EquipmentQueryExecutor
from app.queries.operations import OperationsQueryExecutor
from scripts.query_evaluation_dataset import evidence_matches, load_evaluation, resolve_case


@pytest.mark.integration
@pytest.mark.parametrize(
    "key",
    [
        "q1-positive-unrelated-and-deduplicated",
        "q2-stock-zero-and-unknown",
        "q3-active-boundaries-and-distinct-targets",
        "resolved-unit-incidents",
        "stock-at-reorder-point",
    ],
)
def test_display_labels_match_scoped_records_without_changing_evidence(query_data, key):
    app, owner, manifest, workspaces, _, _ = query_data
    case = next(c for c in load_evaluation().cases if c.key == key)
    with owner.session() as session:
        for facility in session.scalars(
            select(FacilityRecord).where(FacilityRecord.workspace_id == workspaces[1])
        ):
            facility.name = "Other workspace " + facility.code
    for workspace in workspaces:
        expected = resolve_case(case, manifest, workspace)
        operation = expected.expected_plan.operation
        executor = (
            EquipmentQueryExecutor(app)
            if operation in ("facility_equipment", "compatible_stock")
            else OperationsQueryExecutor(app)
        )
        result = executor.execute(
            QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=workspace),
            expected.expected_plan,
            QueryPageRequest(limit=100),
        ).result
        assert evidence_matches(result, expected.expected_result)
        with owner.session() as session:

            def check_record(row, id_key, model, fields):
                identity = row.get(id_key)
                if identity is None:
                    for field in fields:
                        assert row[field] is None
                    return
                record = session.get(model, identity)
                if hasattr(record, "workspace_id"):
                    assert record.workspace_id == workspace
                for field, column in fields.items():
                    assert row[field] == getattr(record, column)

            for row in result.page.rows:
                data = row.model_dump()
                if "facility_id" in data:
                    check_record(
                        data,
                        "facility_id",
                        FacilityRecord,
                        {"facility_name": "name", "facility_code": "code"},
                    )
                if "component_id" in data:
                    check_record(
                        data,
                        "component_id",
                        ComponentRecord,
                        {"component_name": "name", "component_code": "code"},
                    )
                if "model_id" in data:
                    check_record(
                        data,
                        "model_id",
                        EquipmentModelRecord,
                        {"model_name": "name", "model_code": "code"},
                    )
                if operation == "work_orders":
                    check_record(
                        data, "work_order_id", WorkOrderRecord, {"reference_code": "reference_code"}
                    )
                    check_record(
                        data,
                        "originating_incident_id",
                        IncidentRecord,
                        {"originating_incident_code": "reference_code"},
                    )
                    check_record(
                        data,
                        "incident_equipment_unit_id",
                        EquipmentUnitRecord,
                        {"incident_equipment_asset_tag": "asset_tag"},
                    )
                    check_record(
                        data,
                        "target_equipment_unit_id",
                        EquipmentUnitRecord,
                        {"target_equipment_asset_tag": "asset_tag"},
                    )
                if operation == "incidents":
                    check_record(
                        data, "incident_id", IncidentRecord, {"reference_code": "reference_code"}
                    )
                    check_record(data, "unit_id", EquipmentUnitRecord, {"asset_tag": "asset_tag"})
                for unit in data.get("units", []):
                    check_record(unit, "unit_id", EquipmentUnitRecord, {"asset_tag": "asset_tag"})
                for incident in data.get("incidents", []):
                    check_record(
                        incident,
                        "incident_id",
                        IncidentRecord,
                        {"reference_code": "reference_code"},
                    )
            if operation == "compatible_stock":
                assert result.incident_codes == tuple(
                    session.get(IncidentRecord, identity).reference_code
                    for identity in result.incident_ids
                )
