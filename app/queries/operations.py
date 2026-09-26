"""Bounded work-order, incident, and recorded-inventory queries."""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from app.database import Database
from app.equipment.models import (
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
    equipment_model_components,
)
from app.facilities.models import FacilityRecord
from app.operations.models import IncidentRecord, WorkOrderRecord
from app.queries.contracts import (
    EvidencePage,
    FacilityFilter,
    IncidentEvidence,
    IncidentsPlan,
    IncidentsResult,
    InventoryEvidence,
    InventoryPlan,
    InventoryResult,
    QueryContext,
    QueryPageRequest,
    QueryResponse,
    WorkOrderEvidence,
    WorkOrdersPlan,
    WorkOrdersResult,
)
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.execution import pinned_query_session, validate_request


class OperationsQueryExecutor:
    """Execute approved operational filters; caller authorizes the workspace context."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def execute(
        self, context: QueryContext, plan: object, page: QueryPageRequest | None = None
    ) -> QueryResponse:
        context, plan, page = validate_request(context, plan, page)
        if not isinstance(plan, (WorkOrdersPlan, IncidentsPlan, InventoryPlan)):
            raise QueryError(context, QueryErrorKind.INVALID_PLAN)
        with pinned_query_session(self.database, context) as (session, release):
            facilities = self._facility_filters(session, context, plan.facility)
            result: WorkOrdersResult | IncidentsResult | InventoryResult
            if isinstance(plan, WorkOrdersPlan):
                result = self._work(session, context, release, plan, page, facilities)
            elif isinstance(plan, IncidentsPlan):
                result = self._incidents(session, context, release, plan, page, facilities)
            else:
                result = self._inventory(session, context, release, plan, page, facilities)
            return QueryResponse(context=context, catalog_release_id=release, result=result)

    @staticmethod
    def _facility_filters(
        session: Session, context: QueryContext, facility: FacilityFilter
    ) -> list[ColumnElement[bool]]:
        clauses = [FacilityRecord.workspace_id == context.workspace_id]
        if facility.facility_id is not None:
            if (
                session.scalar(
                    select(FacilityRecord.id).where(
                        FacilityRecord.id == facility.facility_id, *clauses
                    )
                )
                is None
            ):
                raise QueryError(context, QueryErrorKind.NOT_FOUND)
            clauses.append(FacilityRecord.id == facility.facility_id)
        if facility.facility_type is not None:
            clauses.append(FacilityRecord.facility_type == facility.facility_type)
        if facility.location is not None:
            clauses.append(FacilityRecord.location == facility.location)
        return clauses

    @staticmethod
    def _require_model(
        session: Session, context: QueryContext, release: UUID, model: UUID | None
    ) -> None:
        if (
            model is not None
            and session.scalar(
                select(EquipmentModelRecord.id).where(
                    EquipmentModelRecord.id == model,
                    EquipmentModelRecord.catalog_release_id == release,
                )
            )
            is None
        ):
            raise QueryError(context, QueryErrorKind.NOT_FOUND)

    @staticmethod
    def _require_unit(
        session: Session, context: QueryContext, release: UUID, unit: UUID | None
    ) -> None:
        if (
            unit is not None
            and session.scalar(
                select(EquipmentUnitRecord.id)
                .join(
                    EquipmentModelRecord,
                    EquipmentModelRecord.id == EquipmentUnitRecord.equipment_model_id,
                )
                .where(
                    EquipmentUnitRecord.id == unit,
                    EquipmentUnitRecord.workspace_id == context.workspace_id,
                    EquipmentModelRecord.catalog_release_id == release,
                )
            )
            is None
        ):
            raise QueryError(context, QueryErrorKind.NOT_FOUND)

    @staticmethod
    def _unit_tag(
        identity: InstrumentedAttribute[UUID | None],
        facility: InstrumentedAttribute[UUID],
        context: QueryContext,
        release: UUID,
    ) -> ColumnElement[str]:
        return (
            select(EquipmentUnitRecord.asset_tag)
            .join(
                EquipmentModelRecord,
                EquipmentModelRecord.id == EquipmentUnitRecord.equipment_model_id,
            )
            .where(
                EquipmentUnitRecord.id == identity,
                EquipmentUnitRecord.facility_id == facility,
                EquipmentUnitRecord.workspace_id == context.workspace_id,
                EquipmentModelRecord.catalog_release_id == release,
            )
            .correlate(WorkOrderRecord, IncidentRecord)
            .scalar_subquery()
        )

    def _work(
        self,
        session: Session,
        context: QueryContext,
        release: UUID,
        plan: WorkOrdersPlan,
        page: QueryPageRequest,
        facilities: list[ColumnElement[bool]],
    ) -> WorkOrdersResult:
        self._require_unit(session, context, release, plan.target_equipment_unit_id)
        if (
            plan.originating_incident_id is not None
            and session.scalar(
                select(IncidentRecord.id).where(
                    IncidentRecord.id == plan.originating_incident_id,
                    IncidentRecord.workspace_id == context.workspace_id,
                )
            )
            is None
        ):
            raise QueryError(context, QueryErrorKind.NOT_FOUND)
        overdue = and_(
            WorkOrderRecord.status.in_(("open", "in_progress", "blocked")),
            WorkOrderRecord.due_at.is_not(None),
            WorkOrderRecord.due_at < plan.as_of,
        )
        query = (
            select(
                WorkOrderRecord.id.label("work_order_id"),
                WorkOrderRecord.reference_code,
                FacilityRecord.name.label("facility_name"),
                FacilityRecord.code.label("facility_code"),
                IncidentRecord.reference_code.label("originating_incident_code"),
                self._unit_tag(
                    IncidentRecord.equipment_unit_id, WorkOrderRecord.facility_id, context, release
                ).label("incident_equipment_asset_tag"),
                self._unit_tag(
                    WorkOrderRecord.target_equipment_unit_id,
                    WorkOrderRecord.facility_id,
                    context,
                    release,
                ).label("target_equipment_asset_tag"),
                WorkOrderRecord.facility_id,
                WorkOrderRecord.status,
                WorkOrderRecord.priority,
                WorkOrderRecord.due_at,
                overdue.label("overdue"),
                (WorkOrderRecord.status == "blocked").label("blocked"),
                WorkOrderRecord.originating_incident_id,
                IncidentRecord.equipment_unit_id.label("incident_equipment_unit_id"),
                WorkOrderRecord.target_equipment_unit_id,
            )
            .join(
                FacilityRecord,
                and_(
                    FacilityRecord.id == WorkOrderRecord.facility_id,
                    FacilityRecord.workspace_id == WorkOrderRecord.workspace_id,
                ),
            )
            .outerjoin(
                IncidentRecord,
                and_(
                    IncidentRecord.id == WorkOrderRecord.originating_incident_id,
                    IncidentRecord.workspace_id == WorkOrderRecord.workspace_id,
                    IncidentRecord.facility_id == WorkOrderRecord.facility_id,
                ),
            )
            .where(WorkOrderRecord.workspace_id == context.workspace_id, *facilities)
        )
        if plan.statuses is not None:
            query = query.where(WorkOrderRecord.status.in_(plan.statuses))
        if plan.priorities is not None:
            query = query.where(WorkOrderRecord.priority.in_(plan.priorities))
        if plan.target_equipment_unit_id is not None:
            query = query.where(
                WorkOrderRecord.target_equipment_unit_id == plan.target_equipment_unit_id
            )
        if plan.originating_incident_id is not None:
            query = query.where(
                WorkOrderRecord.originating_incident_id == plan.originating_incident_id
            )
        if plan.overdue is not None:
            query = query.where(overdue.is_(plan.overdue))
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.execute(
            query.order_by(WorkOrderRecord.reference_code, WorkOrderRecord.id)
            .offset(page.offset)
            .limit(page.limit)
        ).mappings()
        return WorkOrdersResult(
            operation="work_orders",
            page=EvidencePage[WorkOrderEvidence](
                rows=tuple(WorkOrderEvidence.model_validate(row) for row in rows),
                total=total,
                **page.model_dump(),
            ),
        )

    def _incidents(
        self,
        session: Session,
        context: QueryContext,
        release: UUID,
        plan: IncidentsPlan,
        page: QueryPageRequest,
        facilities: list[ColumnElement[bool]],
    ) -> IncidentsResult:
        self._require_unit(session, context, release, plan.equipment_unit_id)
        self._require_model(session, context, release, plan.equipment_model_id)
        query = (
            select(
                IncidentRecord.id.label("incident_id"),
                IncidentRecord.reference_code,
                FacilityRecord.name.label("facility_name"),
                FacilityRecord.code.label("facility_code"),
                self._unit_tag(
                    IncidentRecord.equipment_unit_id, IncidentRecord.facility_id, context, release
                ).label("asset_tag"),
                IncidentRecord.equipment_unit_id.label("unit_id"),
                IncidentRecord.facility_id,
                IncidentRecord.status,
                IncidentRecord.severity,
                IncidentRecord.fault_code,
                IncidentRecord.occurred_at,
            )
            .join(
                FacilityRecord,
                and_(
                    FacilityRecord.workspace_id == IncidentRecord.workspace_id,
                    FacilityRecord.id == IncidentRecord.facility_id,
                ),
            )
            .where(IncidentRecord.workspace_id == context.workspace_id, *facilities)
        )
        if plan.equipment_unit_id is not None:
            query = query.where(IncidentRecord.equipment_unit_id == plan.equipment_unit_id)
        if plan.equipment_model_id is not None:
            query = query.where(
                select(EquipmentUnitRecord.id)
                .where(
                    EquipmentUnitRecord.workspace_id == context.workspace_id,
                    EquipmentUnitRecord.facility_id == IncidentRecord.facility_id,
                    EquipmentUnitRecord.id == IncidentRecord.equipment_unit_id,
                    EquipmentUnitRecord.equipment_model_id == plan.equipment_model_id,
                )
                .exists()
            )
        if plan.statuses is not None:
            query = query.where(IncidentRecord.status.in_(plan.statuses))
        if plan.severities is not None:
            query = query.where(IncidentRecord.severity.in_(plan.severities))
        if plan.fault_code is not None:
            query = query.where(IncidentRecord.fault_code == plan.fault_code)
        if plan.occurred is not None:
            query = query.where(
                IncidentRecord.occurred_at >= plan.occurred.start,
                IncidentRecord.occurred_at < plan.occurred.end,
            )
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.execute(
            query.order_by(IncidentRecord.reference_code, IncidentRecord.id)
            .offset(page.offset)
            .limit(page.limit)
        ).mappings()
        return IncidentsResult(
            operation="incidents",
            count=total,
            page=EvidencePage[IncidentEvidence](
                rows=tuple(IncidentEvidence.model_validate(row) for row in rows),
                total=total,
                **page.model_dump(),
            ),
        )

    def _inventory(
        self,
        session: Session,
        context: QueryContext,
        release: UUID,
        plan: InventoryPlan,
        page: QueryPageRequest,
        facilities: list[ColumnElement[bool]],
    ) -> InventoryResult:
        self._require_model(session, context, release, plan.compatible_model_id)
        if (
            plan.component_id is not None
            and session.scalar(
                select(ComponentRecord.id).where(
                    ComponentRecord.id == plan.component_id,
                    ComponentRecord.catalog_release_id == release,
                )
            )
            is None
        ):
            raise QueryError(context, QueryErrorKind.NOT_FOUND)
        query = (
            select(
                InventoryItemRecord.id.label("inventory_id"),
                FacilityRecord.name.label("facility_name"),
                FacilityRecord.code.label("facility_code"),
                ComponentRecord.name.label("component_name"),
                ComponentRecord.code.label("component_code"),
                InventoryItemRecord.facility_id,
                InventoryItemRecord.component_id,
                InventoryItemRecord.quantity_on_hand,
                InventoryItemRecord.reorder_point,
                func.greatest(
                    0, InventoryItemRecord.reorder_point - InventoryItemRecord.quantity_on_hand
                ).label("shortfall"),
            )
            .join(
                FacilityRecord,
                and_(
                    FacilityRecord.workspace_id == InventoryItemRecord.workspace_id,
                    FacilityRecord.id == InventoryItemRecord.facility_id,
                ),
            )
            .join(ComponentRecord, ComponentRecord.id == InventoryItemRecord.component_id)
            .where(
                InventoryItemRecord.workspace_id == context.workspace_id,
                ComponentRecord.catalog_release_id == release,
                *facilities,
            )
        )
        if plan.component_id is not None:
            query = query.where(InventoryItemRecord.component_id == plan.component_id)
        if plan.compatible_model_id is not None:
            link = equipment_model_components
            query = query.where(
                select(link.c.component_id)
                .where(
                    link.c.catalog_release_id == release,
                    link.c.equipment_model_id == plan.compatible_model_id,
                    link.c.component_id == InventoryItemRecord.component_id,
                )
                .exists()
            )
        if plan.quantity is not None:
            column, value = InventoryItemRecord.quantity_on_hand, plan.quantity.value
            comparisons = {
                "lt": column < value,
                "lte": column <= value,
                "eq": column == value,
                "gte": column >= value,
                "gt": column > value,
            }
            query = query.where(comparisons[plan.quantity.operator])
        if plan.below_reorder_point is not None:
            query = query.where(
                (InventoryItemRecord.quantity_on_hand < InventoryItemRecord.reorder_point).is_(
                    plan.below_reorder_point
                )
            )
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.execute(
            query.order_by(FacilityRecord.code, ComponentRecord.code, InventoryItemRecord.id)
            .offset(page.offset)
            .limit(page.limit)
        ).mappings()
        return InventoryResult(
            operation="inventory",
            page=EvidencePage[InventoryEvidence](
                rows=tuple(InventoryEvidence.model_validate(row) for row in rows),
                total=total,
                **page.model_dump(),
            ),
        )
