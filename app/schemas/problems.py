"""RFC 9457 problem-detail response schema."""

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """Machine-readable error details for HTTP API consumers."""

    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, lt=600)
    detail: str
    instance: str | None = None
