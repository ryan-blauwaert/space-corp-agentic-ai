from uuid import uuid4

import pytest

from app.llm.contracts import ModelCallContext, ModelFinishReason, ModelRequest, ModelResponse
from app.llm.errors import ModelCallError, ModelErrorKind
from app.llm.provider import ModelProvider


class FakeProvider(ModelProvider):
    def __init__(self, failure: ModelErrorKind | None = None) -> None:
        self.failure = failure
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.failure is not None:
            raise ModelCallError(request.context, self.failure)
        return ModelResponse(
            context=request.context, text="Ready", finish_reason=ModelFinishReason.COMPLETED
        )


def request() -> ModelRequest:
    return ModelRequest(
        context=ModelCallContext(
            request_id=uuid4(),
            operation_id=uuid4(),
            model_id="fake",
            prompt_id="smoke",
            prompt_version="1",
        ),
        prompt="Sensitive test content",
        max_output_tokens=16,
        timeout_seconds=5,
    )


def invoke(provider: ModelProvider, call: ModelRequest) -> ModelResponse:
    return provider.generate(call)


def test_provider_can_be_substituted_without_sdk_or_network() -> None:
    fake = FakeProvider()
    call = request()
    response = invoke(fake, call)
    assert response.text == "Ready"
    assert response.context == call.context
    assert fake.requests == [call]


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_failure_preserves_correlation_without_retries(kind: ModelErrorKind) -> None:
    fake = FakeProvider(kind)
    call = request()
    with pytest.raises(ModelCallError) as failure:
        invoke(fake, call)
    assert failure.value.context == call.context
    assert failure.value.kind is kind
    assert fake.requests == [call]
    assert call.prompt not in str(failure.value)
    assert call.prompt not in repr(failure.value)
