import pytest
from pydantic import ValidationError

from app.schemas.pagination import PaginationMetadata


def test_pagination_metadata_serializes_collection_state() -> None:
    metadata = PaginationMetadata(limit=50, offset=0, total=0)

    assert metadata.model_dump() == {"limit": 50, "offset": 0, "total": 0}


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("limit", 0),
        ("limit", 101),
        ("offset", -1),
        ("total", -1),
    ],
)
def test_pagination_metadata_rejects_invalid_bounds(
    field_name: str,
    value: int,
) -> None:
    values = {"limit": 50, "offset": 0, "total": 0}
    values[field_name] = value

    with pytest.raises(ValidationError):
        PaginationMetadata(**values)
