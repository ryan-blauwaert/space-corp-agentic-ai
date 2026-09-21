"""Exact, scoped entity resolution for validated model proposals."""

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import Database
from app.equipment.models import ComponentRecord, EquipmentModelRecord, EquipmentUnitRecord
from app.facilities.models import FacilityRecord
from app.operations.models import IncidentRecord
from app.queries.contracts import PLANNING_OUTCOME, DeclinedPlan, PlanningOutcome, QueryContext
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.execution import pinned_query_session
from app.queries.planning import reference_slots


def _matches(
    session: Session, context: QueryContext, release: UUID, kind: str, reference: str
) -> list[UUID]:
    # Each application-owned statement has a fixed projection and at most two matches.
    record: Any
    if kind == "facility":
        record = FacilityRecord
        names = [record.code, record.name]
        scope = [record.workspace_id == context.workspace_id]
    elif kind == "unit":
        record = EquipmentUnitRecord
        names = [record.asset_tag]
        scope = [
            record.workspace_id == context.workspace_id,
            record.equipment_model_id.in_(
                select(EquipmentModelRecord.id).where(
                    EquipmentModelRecord.catalog_release_id == release
                )
            ),
        ]
    elif kind == "incident":
        record = IncidentRecord
        names = [record.reference_code]
        scope = [record.workspace_id == context.workspace_id]
    else:
        record = EquipmentModelRecord if kind == "model" else ComponentRecord
        names = [record.code, record.name]
        scope = [record.catalog_release_id == release]
    selectors = [func.lower(column) == reference.lower() for column in names]
    try:
        identifier = UUID(reference)
    except ValueError:
        pass
    else:
        selectors.append(record.id == identifier)
    return list(session.scalars(select(record.id).where(*scope, or_(*selectors)).limit(2)))


def resolve_plan(
    database: Database, context: QueryContext, proposal: dict[str, Any]
) -> PlanningOutcome:
    """Resolve only a proposal already accepted by parse_plan; never guess a match."""
    plan = deepcopy(proposal)
    slots = reference_slots(plan)
    if slots:
        with pinned_query_session(database, context) as (session, release):
            for container, key, kind in slots:
                matches = _matches(session, context, release, kind, container[key])
                if not matches:
                    raise QueryError(context, QueryErrorKind.NOT_FOUND)
                if len(matches) > 1:
                    return DeclinedPlan(operation="declined", reason="ambiguous_input")
                container[key] = matches[0]
    return PLANNING_OUTCOME.validate_python(plan)
