from uuid import uuid4

import pytest
from pydantic import ValidationError

from scripts.dataset_manifest import Manifest, load_manifest, operational_id, shared_id


def test_dataset_volume_and_deterministic_identity_contract() -> None:
    manifest = load_manifest()
    assert len(manifest.facilities) == 5
    assert len(manifest.catalog.models) == 12
    assert len(manifest.catalog.components) == 36
    assert len(manifest.units) == len(manifest.incidents) == len(manifest.work_orders) == 60
    assert len(manifest.inventory) == 179
    assert {s.question for s in manifest.scenarios} == {"Q1", "Q2", "Q3", "Q4", "Q5"}
    workspace = uuid4()
    assert operational_id(workspace, "demo-1", "units", "U001") == operational_id(workspace, "demo-1", "units", "U001")
    assert operational_id(workspace, "demo-1", "units", "U001") != operational_id(uuid4(), "demo-1", "units", "U001")
    assert operational_id(workspace, "demo-1", "units", "U001") != operational_id(workspace, "demo-2", "units", "U001")
    assert shared_id("catalog-1", "models", "M01") != shared_id("catalog-2", "models", "M01")


@pytest.mark.parametrize("problem", ["duplicate", "foreign_unit", "compatibility", "stock", "fault", "work_time", "naive", "window"])
def test_invalid_manifest_is_rejected_before_database_access(problem: str) -> None:
    data = load_manifest().model_dump(mode="json")
    if problem == "duplicate":
        data["units"].append(data["units"][0])
    elif problem == "foreign_unit":
        data["incidents"][0]["unit"] = "U013"
    elif problem == "compatibility":
        data["catalog"]["compatibility"][0][1] = "missing"
    elif problem == "stock":
        data["inventory"][0]["quantity_on_hand"] = -1
    elif problem == "fault":
        data["incidents"][0]["fault_code"] = " airflow "
    elif problem == "work_time":
        data["work_orders"][0]["status"] = "completed"
    elif problem == "naive":
        data["as_of"] = "2026-01-31T12:00:00"
    else:
        data["window_start"] = data["as_of"]
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)
