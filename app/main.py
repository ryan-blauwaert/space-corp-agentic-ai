from fastapi import FastAPI, status

from app.config import Settings
from app.schemas.health import HealthResponse

settings = Settings()
app = FastAPI(title=settings.application_name)


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
