"""Read-only Facility API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_database, get_default_workspace_id
from app.database import Database
from app.facilities.repository import SqlAlchemyFacilityRepository
from app.schemas.facilities import FacilityListResponse, FacilityResponse
from app.schemas.pagination import PaginationMetadata, PaginationQuery
from app.schemas.problems import ProblemDetail


router = APIRouter(
    prefix="/facilities",
    tags=["facilities"],
    responses={
        503: {
            "description": "Database or workspace configuration unavailable.",
            "content": {
                "application/problem+json": {"schema": ProblemDetail.model_json_schema()}
            },
        }
    },
)


@router.get(
    "",
    response_model=FacilityListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="listFacilities",
)
def list_facilities(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    pagination: Annotated[PaginationQuery, Query()],
) -> FacilityListResponse:
    with database.workspace_session(workspace_id) as session:
        repository = SqlAlchemyFacilityRepository(session)
        facilities = repository.list_by_workspace(
            workspace_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        total = repository.count_by_workspace(workspace_id)

    return FacilityListResponse(
        items=[FacilityResponse.model_validate(facility) for facility in facilities],
        pagination=PaginationMetadata(
            limit=pagination.limit,
            offset=pagination.offset,
            total=total,
        ),
    )


@router.get(
    "/{facility_id}",
    response_model=FacilityResponse,
    operation_id="getFacility",
    responses={
        404: {
            "description": "Facility not found in the configured workspace.",
            "content": {
                "application/problem+json": {"schema": ProblemDetail.model_json_schema()}
            },
        }
    },
)
def get_facility(
    facility_id: UUID,
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
) -> FacilityResponse:
    with database.workspace_session(workspace_id) as session:
        facility = SqlAlchemyFacilityRepository(session).get_by_id(
            workspace_id, facility_id
        )

    if facility is None:
        raise HTTPException(404, "The requested Facility is not available.")

    return FacilityResponse.model_validate(facility)
