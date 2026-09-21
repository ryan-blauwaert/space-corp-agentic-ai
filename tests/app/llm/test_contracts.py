from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.llm.contracts import (
    ModelCallContext,
    ModelFinishReason,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)


def context() -> ModelCallContext:
    return ModelCallContext(
        request_id=uuid4(),
        operation_id=uuid4(),
        model_id="test-model",
        prompt_id="smoke",
        prompt_version="1",
    )


def test_valid_request_response_and_usage_preserve_identity() -> None:
    identity = context()
    request = ModelRequest(
        context=identity, prompt="Hello", max_output_tokens=16, timeout_seconds=5
    )
    response = ModelResponse(
        context=request.context,
        text="Hello back",
        finish_reason=ModelFinishReason.COMPLETED,
        returned_model_id="test-model-snapshot",
        usage=TokenUsage(input_tokens=3, output_tokens=0),
    )
    assert response.context == identity
    assert response.usage is not None and response.usage.output_tokens == 0
    assert response.returned_model_id == "test-model-snapshot"
    assert ModelRequest.model_validate_json(request.model_dump_json()) == request
    assert ModelResponse.model_validate_json(response.model_dump_json()) == response


@pytest.mark.parametrize("field", ["model_id", "prompt_id", "prompt_version"])
@pytest.mark.parametrize("value", ["", " \n "])
def test_identifiers_must_not_be_blank(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        ModelCallContext.model_validate({**context().model_dump(), field: value})


@pytest.mark.parametrize("field", ["request_id", "operation_id"])
def test_invalid_correlation_ids(field: str) -> None:
    with pytest.raises(ValidationError):
        ModelCallContext.model_validate({**context().model_dump(), field: "not-a-uuid"})


@pytest.mark.parametrize(
    "overrides",
    [
        {"prompt": " "},
        {"max_output_tokens": 0},
        {"max_output_tokens": -1},
        {"max_output_tokens": True},
        {"max_output_tokens": 1.5},
        {"timeout_seconds": 0},
        {"timeout_seconds": -1},
        {"timeout_seconds": True},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": float("nan")},
        {"api_key": "not-allowed"},
    ],
)
def test_invalid_requests(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModelRequest.model_validate(
            {
                "context": context(),
                "prompt": "Hello",
                "max_output_tokens": 16,
                "timeout_seconds": 5,
                **overrides,
            }
        )


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("value", [-1, True, 1.5, "2"])
def test_usage_is_nonnegative_integer_or_unknown(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        TokenUsage.model_validate({field: value})


def test_incomplete_output_and_unknown_usage_are_explicit() -> None:
    response = ModelResponse(
        context=context(), text="Partial", finish_reason=ModelFinishReason.OUTPUT_LIMIT
    )
    assert response.finish_reason == ModelFinishReason.OUTPUT_LIMIT
    assert response.usage is None
    assert response.returned_model_id is None
    assert TokenUsage(input_tokens=0).output_tokens is None


@pytest.mark.parametrize(
    "overrides", [{"text": ""}, {"finish_reason": "unknown"}, {"returned_model_id": " "}]
)
def test_invalid_responses(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModelResponse.model_validate(
            {
                "context": context(),
                "text": "Hello",
                "finish_reason": "completed",
                **overrides,
            }
        )


def test_frozen_contracts_and_content_hidden_from_repr() -> None:
    request = ModelRequest(
        context=context(), prompt="private prompt", max_output_tokens=16, timeout_seconds=5
    )
    response = ModelResponse(
        context=request.context, text="private output", finish_reason=ModelFinishReason.COMPLETED
    )
    assert "private prompt" not in repr(request)
    assert "private output" not in repr(response)
    for model, field, value in (
        (request, "prompt", "Changed"),
        (request.context, "model_id", "Changed"),
        (response, "text", "Changed"),
        (TokenUsage(), "input_tokens", 1),
    ):
        with pytest.raises(ValidationError, match="frozen"):
            setattr(model, field, value)
