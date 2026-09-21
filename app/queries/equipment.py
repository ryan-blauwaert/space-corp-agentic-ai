"""Bounded equipment queries; SQL structure and workspace scope are application-owned."""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.database import Database
from app.equipment.domain import EquipmentOperationalStatus
from app.equipment.models import (
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
    equipment_model_components,
)
from app.facilities.models import FacilityRecord
from app.operations.domain import IncidentStatus
from app.operations.models import IncidentRecord
from app.queries.contracts import (
    CompatibleStockEvidence,
    CompatibleStockPlan,
    CompatibleStockResult,
    EvidencePage,
    FacilityEquipmentEvidence,
    FacilityEquipmentPlan,
    FacilityEquipmentResult,
    QueryContext,
    QueryPageRequest,
    QueryResponse,
    UnitEvidence,
    UnitIncidentEvidence,
)
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.execution import pinned_query_session, validate_request


class EquipmentQueryExecutor:
    """Execute two approved domains in a fresh read-only workspace transaction.

    The caller authorizes QueryContext. This class validates entity visibility and
    catalog pins, not user/session identity. It never accepts caller-supplied SQL.
    """

    def __init__(self, database: Database, *, max_evidence: int = 1000) -> None:
        if type(max_evidence) is not int or not 1 <= max_evidence <= 10000:
            raise ValueError("Evidence limit must be an integer from 1 to 10000.")
        self.database = database
        self.max_evidence = max_evidence

    def execute(
        self, context: QueryContext, plan: object, page: QueryPageRequest | None = None
    ) -> QueryResponse:
        context, plan, page = validate_request(context, plan, page)
        if not isinstance(plan, (FacilityEquipmentPlan, CompatibleStockPlan)):
            raise QueryError(context, QueryErrorKind.INVALID_PLAN)
        with pinned_query_session(self.database, context) as (session, release):
            result = (
                self._facilities(session, context, release, plan, page)
                if isinstance(plan, FacilityEquipmentPlan)
                else self._stock(session, context, release, plan, page)
            )
            return QueryResponse(context=context, catalog_release_id=release, result=result)

    def _check_size(self, size: int, context: QueryContext) -> None:
        if size > self.max_evidence:
            raise QueryError(context, QueryErrorKind.RESOURCE_LIMIT)

    def _facilities(
        self,
        session: Session,
        context: QueryContext,
        release: UUID,
        plan: FacilityEquipmentPlan,
        page: QueryPageRequest,
    ) -> FacilityEquipmentResult:
        workspace = context.workspace_id
        if (
            plan.facility.facility_id is not None
            and session.scalar(
                select(FacilityRecord.id).where(
                    FacilityRecord.workspace_id == workspace,
                    FacilityRecord.id == plan.facility.facility_id,
                )
            )
            is None
        ):
            raise QueryError(context, QueryErrorKind.NOT_FOUND)
        if (
            plan.equipment_model_id is not None
            and session.scalar(
                select(EquipmentModelRecord.id).where(
                    EquipmentModelRecord.id == plan.equipment_model_id,
                    EquipmentModelRecord.catalog_release_id == release,
                )
            )
            is None
        ):
            raise QueryError(context, QueryErrorKind.NOT_FOUND)

        units = (
            select(EquipmentUnitRecord)
            .join(
                EquipmentModelRecord,
                EquipmentModelRecord.id == EquipmentUnitRecord.equipment_model_id,
            )
            .where(
                EquipmentUnitRecord.workspace_id == workspace,
                EquipmentModelRecord.catalog_release_id == release,
            )
        )
        if plan.equipment_model_id is not None:
            units = units.where(EquipmentUnitRecord.equipment_model_id == plan.equipment_model_id)
        if plan.unit_statuses is not None:
            units = units.where(EquipmentUnitRecord.operational_status.in_(plan.unit_statuses))
        if plan.incident_statuses is not None:
            units = units.where(
                select(IncidentRecord.id)
                .where(
                    IncidentRecord.workspace_id == workspace,
                    IncidentRecord.facility_id == EquipmentUnitRecord.facility_id,
                    IncidentRecord.equipment_unit_id == EquipmentUnitRecord.id,
                    IncidentRecord.status.in_(plan.incident_statuses),
                )
                .exists()
            )
        matching_units = units.subquery()
        facilities = select(FacilityRecord).where(
            FacilityRecord.workspace_id == workspace,
            FacilityRecord.id.in_(select(matching_units.c.facility_id)),
        )
        if plan.facility.facility_id is not None:
            facilities = facilities.where(FacilityRecord.id == plan.facility.facility_id)
        if plan.facility.facility_type is not None:
            facilities = facilities.where(
                FacilityRecord.facility_type == plan.facility.facility_type
            )
        if plan.facility.location is not None:
            facilities = facilities.where(FacilityRecord.location == plan.facility.location)
        total = session.scalar(select(func.count()).select_from(facilities.subquery())) or 0
        selected = session.scalars(
            facilities.order_by(FacilityRecord.code, FacilityRecord.id)
            .offset(page.offset)
            .limit(page.limit)
        ).all()
        evidence: list[FacilityEquipmentEvidence] = []
        if selected:
            unit_rows = session.scalars(
                units.where(EquipmentUnitRecord.facility_id.in_([f.id for f in selected]))
                .order_by(EquipmentUnitRecord.asset_tag, EquipmentUnitRecord.id)
                .limit(self.max_evidence + 1)
            ).all()
            self._check_size(len(unit_rows), context)
            incidents = select(IncidentRecord).where(
                IncidentRecord.workspace_id == workspace,
                IncidentRecord.equipment_unit_id.in_([u.id for u in unit_rows]),
            )
            if plan.incident_statuses is not None:
                incidents = incidents.where(IncidentRecord.status.in_(plan.incident_statuses))
            incident_rows = session.scalars(
                incidents.order_by(IncidentRecord.reference_code, IncidentRecord.id).limit(
                    self.max_evidence - len(unit_rows) + 1
                )
            ).all()
            self._check_size(len(unit_rows) + len(incident_rows), context)
            for facility in selected:
                evidence.append(
                    FacilityEquipmentEvidence(
                        facility_id=facility.id,
                        units=tuple(
                            UnitEvidence(
                                unit_id=u.id,
                                operational_status=EquipmentOperationalStatus(u.operational_status),
                            )
                            for u in unit_rows
                            if u.facility_id == facility.id
                        ),
                        incidents=tuple(
                            UnitIncidentEvidence(
                                incident_id=i.id,
                                equipment_unit_id=i.equipment_unit_id,
                                status=IncidentStatus(i.status),
                            )
                            for i in incident_rows
                            if i.facility_id == facility.id and i.equipment_unit_id is not None
                        ),
                    )
                )
        return FacilityEquipmentResult(
            operation="facility_equipment",
            page=EvidencePage[FacilityEquipmentEvidence](
                rows=tuple(evidence), total=total, **page.model_dump()
            ),
        )

    def _stock(
        self,
        session: Session,
        context: QueryContext,
        release: UUID,
        plan: CompatibleStockPlan,
        page: QueryPageRequest,
    ) -> CompatibleStockResult:
        workspace = context.workspace_id
        unit = session.scalar(
            select(EquipmentUnitRecord)
            .join(
                EquipmentModelRecord,
                EquipmentModelRecord.id == EquipmentUnitRecord.equipment_model_id,
            )
            .where(
                EquipmentUnitRecord.id == plan.equipment_unit_id,
                EquipmentUnitRecord.workspace_id == workspace,
                EquipmentModelRecord.catalog_release_id == release,
            )
        )
        if unit is None:
            raise QueryError(context, QueryErrorKind.NOT_FOUND)
        incident_ids: tuple[UUID, ...] = ()
        if plan.incident_statuses is not None:
            incident_ids = tuple(
                session.scalars(
                    select(IncidentRecord.id)
                    .where(
                        IncidentRecord.workspace_id == workspace,
                        IncidentRecord.facility_id == unit.facility_id,
                        IncidentRecord.equipment_unit_id == unit.id,
                        IncidentRecord.status.in_(plan.incident_statuses),
                    )
                    .order_by(IncidentRecord.reference_code, IncidentRecord.id)
                    .limit(self.max_evidence + 1)
                )
            )
            self._check_size(len(incident_ids), context)
            if not incident_ids:
                return CompatibleStockResult(
                    operation="compatible_stock",
                    status="no_incident_match",
                    incident_ids=(),
                    page=EvidencePage[CompatibleStockEvidence](
                        rows=(), total=0, **page.model_dump()
                    ),
                )
        links = equipment_model_components
        stock = (
            select(
                ComponentRecord.id.label("component_id"),
                InventoryItemRecord.id.label("inventory_id"),
                InventoryItemRecord.quantity_on_hand,
            )
            .select_from(ComponentRecord)
            .join(
                links,
                and_(
                    links.c.component_id == ComponentRecord.id,
                    links.c.catalog_release_id == release,
                ),
            )
            .outerjoin(
                InventoryItemRecord,
                and_(
                    InventoryItemRecord.component_id == ComponentRecord.id,
                    InventoryItemRecord.workspace_id == workspace,
                    InventoryItemRecord.facility_id == unit.facility_id,
                ),
            )
            .where(
                links.c.equipment_model_id == unit.equipment_model_id,
                ComponentRecord.catalog_release_id == release,
            )
        )
        total = session.scalar(select(func.count()).select_from(stock.subquery())) or 0
        rows = session.execute(
            stock.order_by(ComponentRecord.code, ComponentRecord.id)
            .offset(page.offset)
            .limit(page.limit)
        ).all()
        self._check_size(len(incident_ids) + len(rows), context)
        return CompatibleStockResult(
            operation="compatible_stock",
            status="matched" if total else "no_compatibility",
            incident_ids=incident_ids,
            page=EvidencePage[CompatibleStockEvidence](
                rows=tuple(
                    CompatibleStockEvidence(model_id=unit.equipment_model_id, **row._mapping)
                    for row in rows
                ),
                total=total,
                **page.model_dump(),
            ),
        )
