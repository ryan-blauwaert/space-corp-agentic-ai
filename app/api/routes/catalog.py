"""Read shared model revisions, component revisions, and compatibility."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_database
from app.database import Database
from app.equipment.repository import SqlAlchemyCatalogRepository
from app.schemas.equipment import (
    CatalogQuery,
    ComponentListResponse,
    ComponentResponse,
    EquipmentModelListResponse,
    EquipmentModelResponse,
)
from app.schemas.pagination import PaginationMetadata, PaginationQuery
from app.schemas.problems import ProblemDetail

CATALOG_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {
        "description": "Shared catalog record not found.",
        "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}},
    },
}

router = APIRouter(
    responses={
        503: {
            "description": "Database unavailable.",
            "content": {"application/problem+json": {"schema": ProblemDetail.model_json_schema()}},
        },
    },
)


@router.get(
    "/equipment-models/{equipment_model_id}",
    response_model=EquipmentModelResponse,
    operation_id="getEquipmentModel",
    tags=["equipment-models"],
    responses=CATALOG_NOT_FOUND,
)
def get_equipment_model(
    equipment_model_id: UUID,
    database: Annotated[Database, Depends(get_database)],
) -> EquipmentModelResponse:
    with database.session() as session:
        model = SqlAlchemyCatalogRepository(session).get_model_by_id(equipment_model_id)
    if model is None:
        raise HTTPException(404, "The requested EquipmentModel is not available.")
    return EquipmentModelResponse.model_validate(model)


@router.get(
    "/components/{component_id}",
    response_model=ComponentResponse,
    operation_id="getComponent",
    tags=["components"],
    responses=CATALOG_NOT_FOUND,
)
def get_component(
    component_id: UUID,
    database: Annotated[Database, Depends(get_database)],
) -> ComponentResponse:
    with database.session() as session:
        component = SqlAlchemyCatalogRepository(session).get_component_by_id(component_id)
    if component is None:
        raise HTTPException(404, "The requested Component is not available.")
    return ComponentResponse.model_validate(component)


@router.get(
    "/equipment-models/{equipment_model_id}/components",
    response_model=ComponentListResponse,
    operation_id="listCompatibleComponents",
    tags=["equipment-models"],
    responses=CATALOG_NOT_FOUND,
)
def list_compatible_components(
    equipment_model_id: UUID,
    database: Annotated[Database, Depends(get_database)],
    query: Annotated[PaginationQuery, Query()],
) -> ComponentListResponse:
    """Compatibility with this exact model revision; does not imply fault repair."""
    with database.session() as session:
        repository = SqlAlchemyCatalogRepository(session)
        if repository.get_model_by_id(equipment_model_id) is None:
            raise HTTPException(404, "The requested EquipmentModel is not available.")
        items, total = repository.read_compatible_components(
            equipment_model_id,
            limit=query.limit,
            offset=query.offset,
        )
    return ComponentListResponse(
        items=[ComponentResponse.model_validate(item) for item in items],
        pagination=PaginationMetadata(limit=query.limit, offset=query.offset, total=total),
    )


@router.get(
    "/equipment-models",
    response_model=EquipmentModelListResponse,
    operation_id="listEquipmentModels",
    tags=["equipment-models"],
)
def list_equipment_models(
    database: Annotated[Database, Depends(get_database)],
    query: Annotated[CatalogQuery, Query()],
) -> EquipmentModelListResponse:
    """Browse shared revisions ordered by code then ID, optionally within a release.

    Unknown release IDs return an empty page. Workspace selection does not restrict
    these shared definitions; totals reflect the release filter before pagination.
    """
    with database.session() as session:
        items, total = SqlAlchemyCatalogRepository(session).read_models_page(
            catalog_release_id=query.catalog_release_id,
            limit=query.limit,
            offset=query.offset,
        )
    return EquipmentModelListResponse(
        items=[EquipmentModelResponse.model_validate(item) for item in items],
        pagination=PaginationMetadata(limit=query.limit, offset=query.offset, total=total),
    )


@router.get(
    "/components",
    response_model=ComponentListResponse,
    operation_id="listComponents",
    tags=["components"],
)
def list_components(
    database: Annotated[Database, Depends(get_database)],
    query: Annotated[CatalogQuery, Query()],
) -> ComponentListResponse:
    """Browse shared revisions ordered by code then ID, optionally within a release.

    Unknown release IDs return an empty page. Workspace selection does not restrict
    these shared definitions; totals reflect the release filter before pagination.
    """
    with database.session() as session:
        items, total = SqlAlchemyCatalogRepository(session).read_components_page(
            catalog_release_id=query.catalog_release_id,
            limit=query.limit,
            offset=query.offset,
        )
    return ComponentListResponse(
        items=[ComponentResponse.model_validate(item) for item in items],
        pagination=PaginationMetadata(limit=query.limit, offset=query.offset, total=total),
    )
