"""Exact, scoped entity resolution for validated model proposals."""

import re
from copy import deepcopy
from typing import Any, Literal
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

EntityKind = Literal["facility", "unit", "incident", "model", "component"]
ENTITY_KINDS: tuple[EntityKind, ...] = ("facility", "unit", "incident", "model", "component")
MAX_GROUNDED_REFERENCES = 16
_UUID_MENTION = re.compile(
    r"(?<![\w-])(?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|[0-9a-f]{32})(?![\w-])",
    re.IGNORECASE,
)


def _entity_scope(
    context: QueryContext, release: UUID, kind: str
) -> tuple[Any, list[Any], list[Any]]:
    """One scope definition for type grounding and final exact resolution."""
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
    elif kind in ("model", "component"):
        record = EquipmentModelRecord if kind == "model" else ComponentRecord
        names = [record.code, record.name]
        scope = [record.catalog_release_id == release]
    else:
        raise ValueError("Unknown entity kind")
    return record, names, scope


def ground_references(
    database: Database, context: QueryContext, question: str
) -> dict[str, list[EntityKind]]:
    """Type only literal UUID mentions; never send a directory or record content to the model."""
    references = dict.fromkeys(_UUID_MENTION.findall(question))
    if len(references) > MAX_GROUNDED_REFERENCES:
        raise QueryError(context, QueryErrorKind.INVALID_PLAN)
    if not references:
        return {}
    identifiers = {UUID(reference) for reference in references}
    kinds: dict[UUID, list[EntityKind]] = {identifier: [] for identifier in identifiers}
    with pinned_query_session(database, context) as (session, release):
        for kind in ENTITY_KINDS:
            record, _, scope = _entity_scope(context, release, kind)
            matches = session.scalars(select(record.id).where(*scope, record.id.in_(identifiers)))
            for identifier in matches:
                kinds[identifier].append(kind)
    return {reference: kinds[UUID(reference)] for reference in references}


def _matches(
    session: Session, context: QueryContext, release: UUID, kind: str, reference: str
) -> list[UUID]:
    # Each application-owned statement has a fixed projection and at most two matches.
    record, names, scope = _entity_scope(context, release, kind)
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
