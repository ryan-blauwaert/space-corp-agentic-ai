"""Read-only equipment-units in the server-configured workspace."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_database, get_default_workspace_id
from app.database import Database
from app.equipment.repository import SqlAlchemyEquipmentUnitRepository
from app.schemas.equipment import EquipmentUnitListResponse, EquipmentUnitQuery, EquipmentUnitResponse
from app.schemas.pagination import PaginationMetadata
from app.schemas.problems import ProblemDetail

router = APIRouter(
    prefix="/equipment-units", tags=["equipment-units"],
    responses={503: {"description": "Database or workspace configuration unavailable.",
        "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}}}},
)


@router.get("", response_model=EquipmentUnitListResponse, operation_id="listEquipmentUnits")
def list_equipment_units(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    query: Annotated[EquipmentUnitQuery, Query()],
) -> EquipmentUnitListResponse:
    """Workspace units ordered by asset tag then ID. Optional filters combine with AND."""
    with database.workspace_session(workspace_id) as session:
        items, total = SqlAlchemyEquipmentUnitRepository(session).read_page(
            workspace_id, limit=query.limit, offset=query.offset,
            facility_id=query.facility_id,
            equipment_model_id=query.equipment_model_id,
            operational_status=query.operational_status,
        )
    return EquipmentUnitListResponse(
        items=[EquipmentUnitResponse.model_validate(item) for item in items],
        pagination=PaginationMetadata(limit=query.limit, offset=query.offset, total=total),
    )


@router.get(
    "/{equipment_unit_id}", response_model=EquipmentUnitResponse, operation_id="getEquipmentUnit",
    responses={404: {"description": "Record not found in the configured workspace.",
        "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}}}},
)
def get_equipment_unit(
    equipment_unit_id: UUID,
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
) -> EquipmentUnitResponse:
    with database.workspace_session(workspace_id) as session:
        item = SqlAlchemyEquipmentUnitRepository(session).get_by_id(workspace_id, equipment_unit_id)
    if item is None:
        raise HTTPException(404, "The requested EquipmentUnit is not available.")
    return EquipmentUnitResponse.model_validate(item)
