"""Read-only incidents in the server-configured workspace."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_database, get_default_workspace_id
from app.database import Database
from app.operations.repository import SqlAlchemyIncidentRepository
from app.schemas.operations import IncidentListResponse, IncidentQuery, IncidentResponse
from app.schemas.pagination import PaginationMetadata
from app.schemas.problems import ProblemDetail

router = APIRouter(
    prefix="/incidents",
    tags=["incidents"],
    responses={
        503: {
            "description": "Database or workspace configuration unavailable.",
            "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}},
        }
    },
)


@router.get("", response_model=IncidentListResponse, operation_id="listIncidents")
def list_incidents(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    query: Annotated[IncidentQuery, Query()],
) -> IncidentListResponse:
    """Workspace incidents ordered by occurrence time then ID. Optional filters combine with AND; time bounds are inclusive from, exclusive before."""
    with database.workspace_session(workspace_id) as session:
        items, total = SqlAlchemyIncidentRepository(session).read_page(
            workspace_id,
            limit=query.limit,
            offset=query.offset,
            facility_id=query.facility_id,
            equipment_unit_id=query.equipment_unit_id,
            status=query.status,
            fault_code=query.fault_code,
            occurred_from=query.occurred_from,
            occurred_before=query.occurred_before,
        )
    return IncidentListResponse(
        items=[IncidentResponse.model_validate(item) for item in items],
        pagination=PaginationMetadata(limit=query.limit, offset=query.offset, total=total),
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    operation_id="getIncident",
    responses={
        404: {
            "description": "Record not found in the configured workspace.",
            "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}},
        }
    },
)
def get_incident(
    incident_id: UUID,
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
) -> IncidentResponse:
    with database.workspace_session(workspace_id) as session:
        item = SqlAlchemyIncidentRepository(session).get_by_id(workspace_id, incident_id)
    if item is None:
        raise HTTPException(404, "The requested Incident is not available.")
    return IncidentResponse.model_validate(item)
