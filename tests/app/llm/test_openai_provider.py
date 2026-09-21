import json
from uuid import uuid4

import httpx
import pytest
from openai import OpenAI

from app.llm.contracts import ModelCallContext, ModelRequest
from app.llm.errors import ModelCallError, ModelErrorKind
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import ModelProvider


@pytest.fixture
def request_value():
    return ModelRequest(
        context=ModelCallContext(
            request_id=uuid4(),
            operation_id=uuid4(),
            model_id="test-model",
            prompt_id="test",
            prompt_version="1",
        ),
        prompt="private prompt",
        max_output_tokens=123,
        timeout_seconds=4.5,
    )


def payload(**overrides):
    return {
        "id": "resp_test",
        "model": "returned-model",
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "usage": None,
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "answer", "annotations": []}],
            }
        ],
        **overrides,
    }


def generate(request_value, handler):
    with OpenAI(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    ) as client:
        provider: ModelProvider = OpenAIProvider(client, "test-model")
        return provider.generate(request_value)


def test_success_sends_bounds_and_preserves_context(request_value):
    def handler(request):
        assert request.url.path == "/v1/responses"
        assert json.loads(request.content) == {
            "model": "test-model",
            "input": "private prompt",
            "max_output_tokens": 123,
            "store": False,
        }
        assert all(value == 4.5 for value in request.extensions["timeout"].values())
        return httpx.Response(200, json=payload(usage={"input_tokens": 0, "output_tokens": 7}))

    response = generate(request_value, handler)
    assert response.context == request_value.context
    assert response.text == "answer"
    assert response.returned_model_id == "returned-model"
    assert response.finish_reason == "completed"
    assert response.usage.input_tokens == 0
    assert response.usage.output_tokens == 7


@pytest.mark.parametrize(
    "usage", [None, {"input_tokens": None, "output_tokens": 2}, {"output_tokens": 2}]
)
def test_unknown_usage_is_not_zero(request_value, usage):
    response = generate(request_value, lambda _: httpx.Response(200, json=payload(usage=usage)))
    if usage is None:
        assert response.usage is None
    else:
        assert response.usage.input_tokens is None


def test_output_limit_is_explicit(request_value):
    response = generate(
        request_value,
        lambda _: httpx.Response(
            200,
            json=payload(status="incomplete", incomplete_details={"reason": "max_output_tokens"}),
        ),
    )
    assert response.finish_reason == "output_limit"


@pytest.mark.parametrize(
    "status,kind",
    [
        (400, "invalid_request"),
        (401, "authentication"),
        (403, "authentication"),
        (404, "invalid_request"),
        (408, "timeout"),
        (409, "unavailable"),
        (422, "invalid_request"),
        (429, "rate_limit"),
        (500, "unavailable"),
        (503, "unavailable"),
    ],
)
def test_http_errors_are_safe_single_attempts(request_value, status, kind):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "private provider detail"}})

    with pytest.raises(ModelCallError) as caught:
        generate(request_value, handler)
    assert len(calls) == 1
    assert caught.value.kind == kind
    assert caught.value.context == request_value.context
    assert str(caught.value) == f"Model call failed: {kind}."
    assert caught.value.__suppress_context__


@pytest.mark.parametrize(
    "exception,kind", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "unavailable")]
)
def test_transport_errors(request_value, exception, kind):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception("private detail", request=request)

    with pytest.raises(ModelCallError) as caught:
        generate(request_value, handler)
    assert caught.value.kind == kind
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body,kind",
    [
        (payload(output=[]), "invalid_response"),
        (payload(output=None), "invalid_response"),
        (payload(output=[{}]), "invalid_response"),
        (payload(output=[{"type": "function_call"}]), "invalid_response"),
        (payload(status="queued"), "invalid_response"),
        (payload(status="incomplete"), "invalid_response"),
        (payload(status="incomplete", incomplete_details={"reason": "content_filter"}), "refused"),
        (payload(error={"code": "server_error", "message": "private"}), "unavailable"),
        (payload(error={"code": "rate_limit_exceeded", "message": "private"}), "rate_limit"),
        (payload(error={"code": "invalid_prompt", "message": "private"}), "invalid_request"),
        (payload(error={"code": "bio_policy", "message": "private"}), "refused"),
        (payload(error={"code": "unknown", "message": "private"}), "invalid_response"),
        (payload(usage={"input_tokens": -1, "output_tokens": 1}), "invalid_response"),
        (
            payload(
                output=[
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "answer"},
                            {"type": "refusal", "refusal": "private"},
                        ],
                    }
                ]
            ),
            "refused",
        ),
        ({}, "invalid_response"),
    ],
)
def test_unusable_responses(request_value, body, kind):
    with pytest.raises(ModelCallError) as caught:
        generate(request_value, lambda _: httpx.Response(200, json=body))
    assert caught.value.kind == kind
    assert caught.value.context == request_value.context
    assert "private" not in str(caught.value)


def test_invalid_json(request_value):
    with pytest.raises(ModelCallError) as caught:
        generate(request_value, lambda _: httpx.Response(200, text="not json"))
    assert caught.value.kind == ModelErrorKind.INVALID_RESPONSE


def test_model_mismatch_prevents_io(request_value):
    request_value = request_value.model_copy(
        update={"context": request_value.context.model_copy(update={"model_id": "different"})}
    )

    def handler(_):
        pytest.fail("Model mismatch must fail before I/O")

    with pytest.raises(ModelCallError) as caught:
        generate(request_value, handler)
    assert caught.value.kind == ModelErrorKind.INVALID_REQUEST


@pytest.mark.parametrize(
    "details,kind",
    [
        ({"code": "insufficient_quota"}, "quota_exceeded"),
        ({"code": "credit_balance_exhausted"}, "quota_exceeded"),
        ({"code": "organization_spend_limit_exceeded"}, "quota_exceeded"),
        ({"code": "project_spend_limit_exceeded"}, "quota_exceeded"),
        ({"code": "organization_usage_limit_exceeded"}, "quota_exceeded"),
        ({"type": "insufficient_quota"}, "quota_exceeded"),
        ({"code": "unknown", "type": "insufficient_quota"}, "quota_exceeded"),
        ({"code": "rate_limit_exceeded", "type": "rate_limit_error"}, "rate_limit"),
        ({"code": "slow_down", "type": "rate_limit_error"}, "rate_limit"),
        ({"code": None, "type": None}, "rate_limit"),
        ({"code": "unknown"}, "rate_limit"),
        ({"code": ["malformed"], "type": {}}, "rate_limit"),
    ],
)
def test_429_uses_structured_quota_identifiers(request_value, details, kind):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "private credentials and insufficient_quota message",
                    **details,
                }
            },
        )

    with pytest.raises(ModelCallError) as caught:
        generate(request_value, handler)
    assert caught.value.kind == kind
    assert caught.value.context == request_value.context
    assert str(caught.value) == f"Model call failed: {kind}."
    assert caught.value.__suppress_context__
    assert len(calls) == 1
