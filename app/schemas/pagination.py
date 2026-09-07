"""Reusable pagination response schemas."""

from pydantic import BaseModel, Field


class PaginationMetadata(BaseModel):
    """Pagination state returned with a collection response."""

    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
