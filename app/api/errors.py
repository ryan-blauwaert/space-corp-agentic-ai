"""HTTP problem responses for expected application failures."""

from http import HTTPStatus

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException

from app.schemas.problems import ProblemDetail


async def http_problem(request: Request, exception: HTTPException) -> JSONResponse:
    problem = ProblemDetail(
        title=HTTPStatus(exception.status_code).phrase,
        status=exception.status_code,
        detail=str(exception.detail),
        instance=request.url.path,
    )
    return JSONResponse(
        problem.model_dump(exclude_none=True),
        status_code=exception.status_code,
        media_type="application/problem+json",
        headers=exception.headers,
    )


async def database_unavailable(
    request: Request, exception: OperationalError
) -> JSONResponse:
    """Keep database connection details out of public error responses."""
    return await http_problem(
        request,
        HTTPException(503, "The Facility API database is unavailable."),
    )
