"""Service health route."""

from fastapi import APIRouter, status

from app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    operation_id="getHealth",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
