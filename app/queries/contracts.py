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

QuestionId = Literal["Q1", "Q2", "Q3", "Q4", "Q5"]
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


class FacilityConditionPlan(Frozen):
    operation: Literal["Q1"]
    facility_id: UUID | None = None


class CompatibleStockPlan(Frozen):
    operation: Literal["Q2"]
    equipment_unit_id: UUID


class PriorityWorkPlan(Frozen):
    operation: Literal["Q3"]
    facility_id: UUID
    as_of: UtcInstant


class FaultRecurrencePlan(Frozen):
    operation: Literal["Q4"]
    equipment_model_id: UUID
    fault_code: FaultCode
    window_start: UtcInstant
    as_of: UtcInstant

    @model_validator(mode="after")
    def valid_window(self) -> "FaultRecurrencePlan":
        if self.window_start >= self.as_of:
            raise ValueError("window_start must precede as_of")
        return self


class StockShortfallPlan(Frozen):
    operation: Literal["Q5"]
    facility_id: UUID


QueryPlan = Annotated[
    FacilityConditionPlan
    | CompatibleStockPlan
    | PriorityWorkPlan
    | FaultRecurrencePlan
    | StockShortfallPlan,
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
    FacilityConditionPlan
    | CompatibleStockPlan
    | PriorityWorkPlan
    | FaultRecurrencePlan
    | StockShortfallPlan
    | DeclinedPlan,
    Field(discriminator="operation"),
]
PLANNING_OUTCOME = TypeAdapter[PlanningOutcome](PlanningOutcome)


T = TypeVar("T")


class EvidencePage(QueryPageRequest, Generic[T]):
    rows: tuple[T, ...]
    total: NonnegativeInt

    @model_validator(mode="after")
    def valid_page(self) -> "EvidencePage[T]":
        if len(self.rows) > min(self.limit, max(0, self.total - self.offset)):
            raise ValueError("Rows exceed the page bounds or total")
        return self


class UnitCondition(Frozen):
    unit_id: UUID
    operational_status: Literal["degraded", "offline"]


class UnresolvedIncident(Frozen):
    incident_id: UUID
    equipment_unit_id: UUID
    status: Literal["open", "investigating"]


class FacilityConditionEvidence(Frozen):
    facility_id: UUID
    units: tuple[UnitCondition, ...] = Field(min_length=1)
    incidents: tuple[UnresolvedIncident, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def matching_units(self) -> "FacilityConditionEvidence":
        units = {unit.unit_id for unit in self.units}
        if len(units) != len(self.units) or units != {i.equipment_unit_id for i in self.incidents}:
            raise ValueError("Each distinct unit must have matching incident evidence")
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


class PriorityWorkEvidence(Frozen):
    work_order_id: UUID
    status: Literal["open", "in_progress", "blocked"]
    priority: Literal["high", "critical"]
    due_at: UtcInstant | None
    overdue: Annotated[bool, Field(strict=True)]
    blocked: Annotated[bool, Field(strict=True)]
    originating_incident_id: UUID | None
    incident_equipment_unit_id: UUID | None
    target_equipment_unit_id: UUID | None

    @model_validator(mode="after")
    def consistent_flags(self) -> "PriorityWorkEvidence":
        if self.blocked != (self.status == "blocked") or (self.due_at is None and self.overdue):
            raise ValueError("Inconsistent work-order flags")
        if self.originating_incident_id is None and self.incident_equipment_unit_id is not None:
            raise ValueError("Affected unit requires an originating incident")
        return self


class FaultOccurrenceEvidence(Frozen):
    incident_id: UUID
    unit_id: UUID
    facility_id: UUID
    occurred_at: UtcInstant


class StockShortfallEvidence(Frozen):
    inventory_id: UUID
    component_id: UUID
    quantity_on_hand: NonnegativeInt
    reorder_point: NonnegativeInt
    shortfall: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def correct_shortfall(self) -> "StockShortfallEvidence":
        if self.shortfall != self.reorder_point - self.quantity_on_hand:
            raise ValueError("Shortfall must equal reorder point minus quantity")
        return self


class FacilityConditionResult(Frozen):
    operation: Literal["Q1"]
    page: EvidencePage[FacilityConditionEvidence]


class CompatibleStockResult(Frozen):
    operation: Literal["Q2"]
    status: Literal["matched", "no_unresolved_incident", "no_compatibility"]
    incident_ids: tuple[UUID, ...]
    page: EvidencePage[CompatibleStockEvidence]

    @model_validator(mode="after")
    def consistent_evidence(self) -> "CompatibleStockResult":
        if len(set(self.incident_ids)) != len(self.incident_ids):
            raise ValueError("Incident evidence must be distinct")
        if (self.status == "no_unresolved_incident") != (not self.incident_ids):
            raise ValueError("Status must agree with supporting incidents")
        if (self.status == "matched") != (self.page.total > 0):
            raise ValueError("Status must agree with compatibility count")
        return self


class PriorityWorkResult(Frozen):
    operation: Literal["Q3"]
    page: EvidencePage[PriorityWorkEvidence]


class FaultRecurrenceResult(Frozen):
    operation: Literal["Q4"]
    count: NonnegativeInt
    repeated: Annotated[bool, Field(strict=True)]
    page: EvidencePage[FaultOccurrenceEvidence]

    @model_validator(mode="after")
    def correct_count(self) -> "FaultRecurrenceResult":
        if self.count != self.page.total or self.repeated != (self.count >= 2):
            raise ValueError("Recurrence uses the total distinct incident count, not page length")
        if len({row.incident_id for row in self.page.rows}) != len(self.page.rows):
            raise ValueError("Incident evidence must be distinct")
        return self


class StockShortfallResult(Frozen):
    operation: Literal["Q5"]
    page: EvidencePage[StockShortfallEvidence]


QueryResult = Annotated[
    FacilityConditionResult
    | CompatibleStockResult
    | PriorityWorkResult
    | FaultRecurrenceResult
    | StockShortfallResult,
    Field(discriminator="operation"),
]
QUERY_RESULT = TypeAdapter[QueryResult](QueryResult)


class QueryResponse(Frozen):
    context: QueryContext
    catalog_release_id: UUID
    result: QueryResult = Field(repr=False)
