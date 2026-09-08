"""Read-only Facility API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_database, get_default_workspace_id
from app.database import Database
from app.facilities.repository import SqlAlchemyFacilityRepository
from app.schemas.facilities import FacilityListResponse, FacilityResponse
from app.schemas.pagination import PaginationMetadata


router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get(
    "",
    response_model=FacilityListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="listFacilities",
)
def list_facilities(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FacilityListResponse:
    with database.workspace_session(workspace_id) as session:
        repository = SqlAlchemyFacilityRepository(session)
        facilities = repository.list_by_workspace(
            workspace_id,
            limit=limit,
            offset=offset,
        )
        total = repository.count_by_workspace(workspace_id)

    return FacilityListResponse(
        items=[FacilityResponse.model_validate(facility) for facility in facilities],
        pagination=PaginationMetadata(limit=limit, offset=offset, total=total),
    )
