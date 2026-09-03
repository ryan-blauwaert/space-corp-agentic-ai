from fastapi import FastAPI, status

from app.schemas.health import HealthResponse

app = FastAPI()


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
