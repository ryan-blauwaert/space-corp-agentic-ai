"""Read-only inventory-items in the server-configured workspace."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_database, get_default_workspace_id
from app.database import Database
from app.equipment.repository import SqlAlchemyInventoryItemRepository
from app.schemas.equipment import InventoryItemListResponse, InventoryItemQuery, InventoryItemResponse
from app.schemas.pagination import PaginationMetadata
from app.schemas.problems import ProblemDetail

router = APIRouter(
    prefix="/inventory-items", tags=["inventory-items"],
    responses={503: {"description": "Database or workspace configuration unavailable.",
        "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}}}},
)


@router.get("", response_model=InventoryItemListResponse, operation_id="listInventoryItems")
def list_inventory_items(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    query: Annotated[InventoryItemQuery, Query()],
) -> InventoryItemListResponse:
    """Recorded workspace stock ordered by ID. Missing stock rows are not zero quantities. Optional filters combine with AND."""
    with database.workspace_session(workspace_id) as session:
        items, total = SqlAlchemyInventoryItemRepository(session).read_page(
            workspace_id, limit=query.limit, offset=query.offset,
            facility_id=query.facility_id,
            component_id=query.component_id,
        )
    return InventoryItemListResponse(
        items=[InventoryItemResponse.model_validate(item) for item in items],
        pagination=PaginationMetadata(limit=query.limit, offset=query.offset, total=total),
    )


@router.get(
    "/{inventory_item_id}", response_model=InventoryItemResponse, operation_id="getInventoryItem",
    responses={404: {"description": "Record not found in the configured workspace.",
        "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}}}},
)
def get_inventory_item(
    inventory_item_id: UUID,
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
) -> InventoryItemResponse:
    with database.workspace_session(workspace_id) as session:
        item = SqlAlchemyInventoryItemRepository(session).get_by_id(workspace_id, inventory_item_id)
    if item is None:
        raise HTTPException(404, "The requested InventoryItem is not available.")
    return InventoryItemResponse.model_validate(item)
