"""Query values only: validating a plan neither authorizes nor executes it."""

from datetime import UTC, datetime
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)

from app.equipment.domain import EquipmentOperationalStatus
from app.facilities.domain import FacilityType
from app.operations.domain import (
    IncidentSeverity,
    IncidentStatus,
    WorkOrderPriority,
    WorkOrderStatus,
)

NonnegativeInt = Annotated[int, Field(ge=0, strict=True)]


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _normalize_fault(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


UtcInstant = Annotated[AwareDatetime, AfterValidator(_utc)]
FaultCode = Annotated[
    str, BeforeValidator(_normalize_fault), Field(min_length=1, max_length=64, pattern=r"\S")
]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QueryContext(Frozen):
    """Trusted caller metadata; never populated from model-generated plan fields."""

    request_id: UUID
    operation_id: UUID
    workspace_id: UUID


class QueryPageRequest(Frozen):
    """Caller-owned bounds matching the existing API's 50/100 limit convention."""

    limit: int = Field(default=50, ge=1, le=100, strict=True)
    offset: NonnegativeInt = 0


class FacilityFilter(Frozen):
    """All supplied selectors intersect; location is an exact stored value."""

    facility_id: UUID | None = None
    facility_type: FacilityType | None = Field(
        default=None,
        description="Select all facilities of this type; no individual facility ID is needed.",
    )
    location: str | None = Field(default=None, min_length=1, max_length=256, pattern=r"\S")


T = TypeVar("T")

Selection = Annotated[
    tuple[T, ...],
    Field(min_length=1, max_length=20),
    AfterValidator(lambda v: tuple(dict.fromkeys(v))),
]


class TimeWindow(Frozen):
    start: UtcInstant
    end: UtcInstant

    @model_validator(mode="after")
    def valid_window(self) -> "TimeWindow":
        if self.start >= self.end:
            raise ValueError("start must precede end")
        return self


class QuantityFilter(Frozen):
    operator: Literal["lt", "lte", "eq", "gte", "gt"] = Field(
        description="Comparison against quantity_on_hand: lt means <, lte <=, eq =, gte >=, gt >. "
        "Quantities are integers >= 0. Any complete set {0, ..., N} is exactly lte N "
        "(equivalently lt N+1), including when expressed as alternatives in ordinary language."
    )
    value: NonnegativeInt = Field(
        description="The integer bound, not a component count or reorder point."
    )


class FacilityEquipmentPlan(Frozen):
    operation: Literal["facility_equipment"]
    facility: FacilityFilter = Field(default_factory=FacilityFilter)
    equipment_model_id: UUID | None = None
    unit_statuses: Selection[EquipmentOperationalStatus] | None = None
    incident_statuses: Selection[IncidentStatus] | None = None


class CompatibleStockPlan(Frozen):
    operation: Literal["compatible_stock"]
    equipment_unit_id: UUID
    incident_statuses: Selection[IncidentStatus] | None = None


class WorkOrdersPlan(Frozen):
    operation: Literal["work_orders"]
    facility: FacilityFilter = Field(default_factory=FacilityFilter)
    statuses: Selection[WorkOrderStatus] | None = None
    priorities: Selection[WorkOrderPriority] | None = None
    target_equipment_unit_id: UUID | None = None
    originating_incident_id: UUID | None = None
    as_of: UtcInstant
    overdue: Annotated[bool, Field(strict=True)] | None = None


class IncidentsPlan(Frozen):
    operation: Literal["incidents"]
    facility: FacilityFilter = Field(default_factory=FacilityFilter)
    equipment_unit_id: UUID | None = None
    equipment_model_id: UUID | None = None
    statuses: Selection[IncidentStatus] | None = None
    severities: Selection[IncidentSeverity] | None = None
    fault_code: FaultCode | None = None
    occurred: TimeWindow | None = None


class InventoryPlan(Frozen):
    operation: Literal["inventory"]
    facility: FacilityFilter = Field(default_factory=FacilityFilter)
    component_id: UUID | None = None
    compatible_model_id: UUID | None = None
    quantity: QuantityFilter | None = None
    below_reorder_point: Annotated[bool, Field(strict=True)] | None = None


QueryPlan = Annotated[
    FacilityEquipmentPlan | CompatibleStockPlan | WorkOrdersPlan | IncidentsPlan | InventoryPlan,
    Field(discriminator="operation"),
]
QUERY_PLAN = TypeAdapter[QueryPlan](QueryPlan)


class DeclinedPlan(Frozen):
    """Terminal planning outcome; does not authorize partial query execution."""

    operation: Literal["declined"]
    reason: Literal[
        "unsupported_question", "prohibited_operation", "missing_input", "ambiguous_input"
    ]


PlanningOutcome = Annotated[
    FacilityEquipmentPlan
    | CompatibleStockPlan
    | WorkOrdersPlan
    | IncidentsPlan
    | InventoryPlan
    | DeclinedPlan,
    Field(discriminator="operation"),
]
PLANNING_OUTCOME = TypeAdapter[PlanningOutcome](PlanningOutcome)


class EvidencePage(QueryPageRequest, Generic[T]):
    rows: tuple[T, ...]
    total: NonnegativeInt

    @model_validator(mode="after")
    def valid_page(self) -> "EvidencePage[T]":
        if len(self.rows) > min(self.limit, max(0, self.total - self.offset)):
            raise ValueError("Rows exceed the page bounds or total")
        return self


class UnitEvidence(Frozen):
    unit_id: UUID
    operational_status: EquipmentOperationalStatus


class UnitIncidentEvidence(Frozen):
    incident_id: UUID
    equipment_unit_id: UUID
    status: IncidentStatus


class FacilityEquipmentEvidence(Frozen):
    facility_id: UUID
    units: tuple[UnitEvidence, ...] = Field(min_length=1)
    incidents: tuple[UnitIncidentEvidence, ...]

    @model_validator(mode="after")
    def matching_units(self) -> "FacilityEquipmentEvidence":
        units = {unit.unit_id for unit in self.units}
        if len(units) != len(self.units) or not {
            i.equipment_unit_id for i in self.incidents
        }.issubset(units):
            raise ValueError("Incident evidence must refer to distinct listed units")
        if len({i.incident_id for i in self.incidents}) != len(self.incidents):
            raise ValueError("Incident evidence must be distinct")
        return self


class CompatibleStockEvidence(Frozen):
    model_id: UUID
    component_id: UUID
    inventory_id: UUID | None
    quantity_on_hand: NonnegativeInt | None

    @model_validator(mode="after")
    def inventory_presence(self) -> "CompatibleStockEvidence":
        if (self.inventory_id is None) != (self.quantity_on_hand is None):
            raise ValueError("Missing inventory and quantity must both be null")
        return self


class WorkOrderEvidence(Frozen):
    work_order_id: UUID
    facility_id: UUID
    status: WorkOrderStatus
    priority: WorkOrderPriority
    due_at: UtcInstant | None
    overdue: Annotated[bool, Field(strict=True)]
    blocked: Annotated[bool, Field(strict=True)]
    originating_incident_id: UUID | None
    incident_equipment_unit_id: UUID | None
    target_equipment_unit_id: UUID | None

    @model_validator(mode="after")
    def consistent_flags(self) -> "WorkOrderEvidence":
        if self.blocked != (self.status == "blocked") or (
            self.overdue and (self.due_at is None or self.status in ("completed", "cancelled"))
        ):
            raise ValueError("Inconsistent work-order flags")
        if self.originating_incident_id is None and self.incident_equipment_unit_id is not None:
            raise ValueError("Affected unit requires an originating incident")
        return self


class IncidentEvidence(Frozen):
    incident_id: UUID
    status: IncidentStatus
    severity: IncidentSeverity
    fault_code: FaultCode | None
    unit_id: UUID | None
    facility_id: UUID
    occurred_at: UtcInstant


class InventoryEvidence(Frozen):
    inventory_id: UUID
    facility_id: UUID
    component_id: UUID
    quantity_on_hand: NonnegativeInt
    reorder_point: NonnegativeInt
    shortfall: NonnegativeInt

    @model_validator(mode="after")
    def correct_shortfall(self) -> "InventoryEvidence":
        if self.shortfall != max(0, self.reorder_point - self.quantity_on_hand):
            raise ValueError("Shortfall must equal max(0, reorder point minus quantity)")
        return self


class FacilityEquipmentResult(Frozen):
    operation: Literal["facility_equipment"]
    page: EvidencePage[FacilityEquipmentEvidence]


class CompatibleStockResult(Frozen):
    operation: Literal["compatible_stock"]
    status: Literal["matched", "no_incident_match", "no_compatibility"]
    incident_ids: tuple[UUID, ...]
    page: EvidencePage[CompatibleStockEvidence]

    @model_validator(mode="after")
    def consistent_evidence(self) -> "CompatibleStockResult":
        if len(set(self.incident_ids)) != len(self.incident_ids):
            raise ValueError("Incident evidence must be distinct")
        if self.status == "no_incident_match" and self.incident_ids:
            raise ValueError("Status must agree with supporting incidents")
        if (self.status == "matched") != (self.page.total > 0):
            raise ValueError("Status must agree with compatibility count")
        return self


class WorkOrdersResult(Frozen):
    operation: Literal["work_orders"]
    page: EvidencePage[WorkOrderEvidence]


class IncidentsResult(Frozen):
    operation: Literal["incidents"]
    count: NonnegativeInt
    page: EvidencePage[IncidentEvidence]

    @model_validator(mode="after")
    def correct_count(self) -> "IncidentsResult":
        if self.count != self.page.total:
            raise ValueError("Count uses the total distinct incidents, not page length")
        if len({row.incident_id for row in self.page.rows}) != len(self.page.rows):
            raise ValueError("Incident evidence must be distinct")
        return self


class InventoryResult(Frozen):
    operation: Literal["inventory"]
    page: EvidencePage[InventoryEvidence]


QueryResult = Annotated[
    FacilityEquipmentResult
    | CompatibleStockResult
    | WorkOrdersResult
    | IncidentsResult
    | InventoryResult,
    Field(discriminator="operation"),
]
QUERY_RESULT = TypeAdapter[QueryResult](QueryResult)


class QueryResponse(Frozen):
    context: QueryContext
    catalog_release_id: UUID
    result: QueryResult = Field(repr=False)
