import pytest
from pydantic import ValidationError

from app.schemas.problems import ProblemDetail


def test_problem_detail_uses_the_standard_default_type() -> None:
    problem = ProblemDetail(
        title="Facility not found",
        status=404,
        detail="The requested Facility is not available.",
    )

    assert problem.model_dump() == {
        "type": "about:blank",
        "title": "Facility not found",
        "status": 404,
        "detail": "The requested Facility is not available.",
        "instance": None,
    }


def test_problem_detail_preserves_a_custom_problem_type_uri() -> None:
    problem = ProblemDetail(
        type="https://space-corp.example/problems/facility-not-found",
        title="Facility not found",
        status=404,
        detail="The requested Facility is not available.",
    )

    assert problem.type == "https://space-corp.example/problems/facility-not-found"


@pytest.mark.parametrize("status", [399, 600])
def test_problem_detail_rejects_non_error_status_codes(status: int) -> None:
    with pytest.raises(ValidationError):
        ProblemDetail(title="Invalid", status=status, detail="Invalid status.")


@pytest.mark.parametrize("status", [400, 599])
def test_problem_detail_accepts_error_status_boundaries(status: int) -> None:
    problem = ProblemDetail(title="Valid", status=status, detail="Valid status.")

    assert problem.status == status
