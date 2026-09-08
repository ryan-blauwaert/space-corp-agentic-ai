"""Reusable pagination request and response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class PaginationQuery(BaseModel):
    """Validated pagination parameters accepted from API consumers."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginationMetadata(BaseModel):
    """Pagination state returned with a collection response."""

    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
