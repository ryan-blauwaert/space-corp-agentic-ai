"""Read-only work-orders in the server-configured workspace."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_database, get_default_workspace_id
from app.database import Database
from app.operations.repository import SqlAlchemyWorkOrderRepository
from app.schemas.operations import WorkOrderListResponse, WorkOrderQuery, WorkOrderResponse
from app.schemas.pagination import PaginationMetadata
from app.schemas.problems import ProblemDetail

router = APIRouter(
    prefix="/work-orders", tags=["work-orders"],
    responses={503: {"description": "Database or workspace configuration unavailable.",
        "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}}}},
)


@router.get("", response_model=WorkOrderListResponse, operation_id="listWorkOrders")
def list_work_orders(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
    query: Annotated[WorkOrderQuery, Query()],
) -> WorkOrderListResponse:
    """Workspace work orders ordered by reference code then ID. Optional filters combine with AND. Due times are returned without an implicit current-time overdue calculation."""
    with database.workspace_session(workspace_id) as session:
        items, total = SqlAlchemyWorkOrderRepository(session).read_page(
            workspace_id, limit=query.limit, offset=query.offset,
            facility_id=query.facility_id,
            status=query.status,
            priority=query.priority,
        )
    return WorkOrderListResponse(
        items=[WorkOrderResponse.model_validate(item) for item in items],
        pagination=PaginationMetadata(limit=query.limit, offset=query.offset, total=total),
    )


@router.get(
    "/{work_order_id}", response_model=WorkOrderResponse, operation_id="getWorkOrder",
    responses={404: {"description": "Record not found in the configured workspace.",
        "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}}}},
)
def get_work_order(
    work_order_id: UUID,
    database: Annotated[Database, Depends(get_database)],
    workspace_id: Annotated[UUID, Depends(get_default_workspace_id)],
) -> WorkOrderResponse:
    with database.workspace_session(workspace_id) as session:
        item = SqlAlchemyWorkOrderRepository(session).get_by_id(workspace_id, work_order_id)
    if item is None:
        raise HTTPException(404, "The requested WorkOrder is not available.")
    return WorkOrderResponse.model_validate(item)
