"""Validated, immutable input contracts for the versioned local demo dataset."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, TypeVar
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator

from app.equipment.domain import EquipmentOperationalStatus
from app.facilities.domain import FacilityOperationalStatus, FacilityType
from app.operations.domain import IncidentSeverity, IncidentStatus, WorkOrderPriority, WorkOrderStatus

Key = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "data/baselines/demo-1.json"


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Keyed(Frozen):
    key: Key


T = TypeVar("T", bound=Keyed)


class Named(Keyed):
    name: str = Field(min_length=1, max_length=256, pattern=r"\S")


class Catalog(Frozen):
    version: Key
    models: tuple[Named, ...]
    components: tuple[Named, ...]
    compatibility: tuple[tuple[Key, Key], ...]


class Facility(Named):
    facility_type: FacilityType
    location: str = Field(min_length=1, max_length=256, pattern=r"\S")
    operational_status: FacilityOperationalStatus


class Unit(Keyed):
    facility: Key
    model: Key
    operational_status: EquipmentOperationalStatus


class Inventory(Keyed):
    facility: Key
    component: Key
    quantity_on_hand: int = Field(ge=0, strict=True)
    reorder_point: int = Field(ge=0, strict=True)


class Incident(Keyed):
    facility: Key
    unit: Key | None
    severity: IncidentSeverity
    status: IncidentStatus
    occurred_at: AwareDatetime
    fault_code: str | None
    resolved_at: AwareDatetime | None


class WorkOrder(Keyed):
    facility: Key
    incident: Key | None
    target: Key | None
    priority: WorkOrderPriority
    status: WorkOrderStatus
    due_at: AwareDatetime | None
    completed_at: AwareDatetime | None


class Scenario(Keyed):
    question: Literal["Q1", "Q2", "Q3", "Q4", "Q5"]
    inputs: dict[str, str]
    expected: dict[str, object]


class Manifest(Frozen):
    version: Key
    created_at: AwareDatetime
    as_of: AwareDatetime
    window_start: AwareDatetime
    catalog: Catalog
    facilities: tuple[Facility, ...]
    units: tuple[Unit, ...]
    inventory: tuple[Inventory, ...]
    incidents: tuple[Incident, ...]
    work_orders: tuple[WorkOrder, ...]
    scenarios: tuple[Scenario, ...]

    @model_validator(mode="after")
    def validate_references(self) -> "Manifest":
        def keyed(rows: tuple[T, ...]) -> dict[str, T]:
            result = {row.key: row for row in rows}
            if len(result) != len(rows):
                raise ValueError("Duplicate entity key")
            return result

        facilities = keyed(self.facilities)
        models = keyed(self.catalog.models)
        components = keyed(self.catalog.components)
        units = keyed(self.units)
        incidents = keyed(self.incidents)
        keyed(self.inventory)
        keyed(self.work_orders)
        keyed(self.scenarios)
        if not self.created_at <= self.window_start < self.as_of:
            raise ValueError("Invalid baseline time window")
        if len(set(self.catalog.compatibility)) != len(self.catalog.compatibility):
            raise ValueError("Duplicate compatibility pair")
        for model, component in self.catalog.compatibility:
            if model not in models or component not in components:
                raise ValueError("Unknown compatibility reference")
        for unit in self.units:
            if unit.facility not in facilities or unit.model not in models:
                raise ValueError("Unknown unit reference")
        stock_keys = set()
        for stock in self.inventory:
            if stock.facility not in facilities or stock.component not in components:
                raise ValueError("Unknown inventory reference")
            pair = (stock.facility, stock.component)
            if pair in stock_keys:
                raise ValueError("Duplicate facility/component stock")
            stock_keys.add(pair)
        for incident in self.incidents:
            if incident.facility not in facilities:
                raise ValueError("Unknown incident Facility")
            if incident.unit is not None and (incident.unit not in units or units[incident.unit].facility != incident.facility):
                raise ValueError("Incident unit must share Facility")
            if (incident.status == IncidentStatus.RESOLVED) != (incident.resolved_at is not None):
                raise ValueError("Invalid incident terminal time")
            if incident.resolved_at is not None and incident.resolved_at < incident.occurred_at:
                raise ValueError("Incident resolution precedes occurrence")
            if incident.fault_code is not None and (not incident.fault_code.strip() or incident.fault_code != incident.fault_code.strip().upper() or len(incident.fault_code) > 64):
                raise ValueError("Fault code must be normalized")
        for work in self.work_orders:
            if work.facility not in facilities:
                raise ValueError("Unknown work-order Facility")
            for key, records in ((work.incident, incidents), (work.target, units)):
                if key is not None and (key not in records or records[key].facility != work.facility):
                    raise ValueError("Work-order reference must share Facility")
            if (work.status == WorkOrderStatus.COMPLETED) != (work.completed_at is not None):
                raise ValueError("Invalid work-order terminal time")
            if work.completed_at is not None and work.completed_at < self.created_at:
                raise ValueError("Completion precedes baseline creation")
        return self


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Manifest:
    return Manifest.model_validate_json(path.read_text())


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def shared_id(version: str, entity: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, json.dumps(["space-corp", version, entity, key], separators=(",", ":")))


def operational_id(workspace: UUID, baseline: str, entity: str, key: str) -> UUID:
    """UUIDv5 name encoding: compact JSON array [baseline version, entity, key]."""
    return uuid5(workspace, json.dumps([baseline, entity, key], separators=(",", ":")))
