import json
import logging
from uuid import uuid4

import httpx
import pytest
from openai import OpenAI

from app.llm.contracts import (
    ModelCallContext,
    ModelFinishReason,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)
from app.llm.errors import ModelCallError, ModelErrorKind
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import ModelProvider
from app.llm.service import ModelService


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []
        self.windows = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def uniform(self, lower, upper):
        self.windows.append((lower, upper))
        return upper


class ScriptedProvider(ModelProvider):
    def __init__(self, outcomes, timer):
        self.outcomes = iter(outcomes)
        self.timer = timer
        self.requests = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        self.timer.now += 0.25
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def call():
    return ModelRequest(
        context=ModelCallContext(
            request_id=uuid4(),
            operation_id=uuid4(),
            model_id="configured-model",
            prompt_id="smoke",
            prompt_version="1",
        ),
        prompt="SECRET prompt and operational evidence",
        max_output_tokens=32,
        timeout_seconds=2,
    )


def result(call, **overrides):
    return ModelResponse(
        context=call.context,
        text="SECRET model output",
        finish_reason=ModelFinishReason.COMPLETED,
        **overrides,
    )


@pytest.fixture(autouse=True)
def enable_telemetry(caplog):
    caplog.set_level(logging.INFO, logger="app.llm.service")


def events(caplog):
    records = [record for record in caplog.records if record.name == "app.llm.service"]
    assert all(record.exc_info is None and record.stack_info is None for record in records)
    return [json.loads(record.getMessage()) for record in records]


def setup_service(outcomes, **options):
    timer = FakeTime()
    provider = ScriptedProvider(outcomes, timer)
    service = ModelService(
        provider, clock=timer.clock, sleep=timer.sleep, uniform=timer.uniform, **options
    )
    return service, provider, timer


def test_success_logs_allowlisted_correlated_metadata(call, caplog):
    response = result(
        call, returned_model_id="returned-model", usage=TokenUsage(input_tokens=0, output_tokens=7)
    )
    service, provider, timer = setup_service([response])
    assert service.generate(call) is response
    assert provider.requests == [call]
    assert timer.sleeps == []
    attempt, operation = events(caplog)
    assert attempt["event"] == "model_attempt"
    assert operation["event"] == "model_operation"
    for entry in (attempt, operation):
        assert entry == {
            "event": entry["event"],
            "request_id": str(call.context.request_id),
            "operation_id": str(call.context.operation_id),
            "model_id": "configured-model",
            "prompt_id": "smoke",
            "prompt_version": "1",
            "attempt_count": 1,
            "duration_ms": 250.0,
            "outcome": "completed",
            "error_kind": None,
            "returned_model_id": "returned-model",
            "input_tokens": 0,
            "output_tokens": 7,
        }
    assert "SECRET" not in caplog.text


@pytest.mark.parametrize(
    "kind", [ModelErrorKind.RATE_LIMIT, ModelErrorKind.TIMEOUT, ModelErrorKind.UNAVAILABLE]
)
def test_transient_failure_retries_same_request_then_succeeds(call, caplog, kind):
    response = result(call)
    service, provider, timer = setup_service([ModelCallError(call.context, kind), response])
    assert service.generate(call) is response
    assert len(provider.requests) == 2
    assert all(request is call for request in provider.requests)
    assert timer.windows == [(0.0, 0.5)]
    assert timer.sleeps == [0.5]
    first, second, operation = events(caplog)
    assert first["error_kind"] == kind
    assert first["outcome"] == "failed"
    assert first["duration_ms"] == second["duration_ms"] == 250.0
    assert operation["attempt_count"] == 2
    assert operation["duration_ms"] == 1000.0
    assert operation["outcome"] == "completed"
    assert operation["input_tokens"] is None
    assert operation["output_tokens"] is None
    assert all(
        entry["operation_id"] == str(call.context.operation_id)
        and entry["request_id"] == str(call.context.request_id)
        for entry in events(caplog)
    )


@pytest.mark.parametrize(
    "kind", [ModelErrorKind.RATE_LIMIT, ModelErrorKind.TIMEOUT, ModelErrorKind.UNAVAILABLE]
)
def test_retry_exhaustion_is_bounded(call, caplog, kind):
    failures = [ModelCallError(call.context, kind) for _ in range(3)]
    service, provider, timer = setup_service(failures)
    with pytest.raises(ModelCallError) as caught:
        service.generate(call)
    assert caught.value is failures[-1]
    assert len(provider.requests) == 3
    assert timer.windows == [(0.0, 0.5), (0.0, 1.0)]
    assert timer.sleeps == [0.5, 1.0]
    entries = events(caplog)
    assert [entry["event"] for entry in entries] == ["model_attempt"] * 3 + ["model_operation"]
    assert entries[-1]["attempt_count"] == 3
    assert entries[-1]["duration_ms"] == 2250.0
    assert entries[-1]["error_kind"] == kind
    assert all(entry["outcome"] == "failed" for entry in entries)


@pytest.mark.parametrize(
    "kind",
    [
        ModelErrorKind.AUTHENTICATION,
        ModelErrorKind.QUOTA_EXCEEDED,
        ModelErrorKind.INVALID_REQUEST,
        ModelErrorKind.INVALID_RESPONSE,
        ModelErrorKind.REFUSED,
    ],
)
def test_permanent_failure_is_not_retried(call, caplog, kind):
    failure = ModelCallError(call.context, kind)
    # Even unexpectedly sensitive exception args must not reach service telemetry.
    failure.args = ("SECRET provider message and credentials",)
    service, provider, timer = setup_service([failure])
    with pytest.raises(ModelCallError) as caught:
        service.generate(call)
    assert caught.value is failure
    assert len(provider.requests) == 1
    assert timer.sleeps == []
    entries = events(caplog)
    assert len(entries) == 2
    assert all(entry["error_kind"] == kind for entry in entries)
    assert "SECRET" not in caplog.text


def test_one_attempt_disables_retry(call, caplog):
    service, provider, timer = setup_service(
        [ModelCallError(call.context, ModelErrorKind.TIMEOUT)], max_attempts=1
    )
    with pytest.raises(ModelCallError):
        service.generate(call)
    assert len(provider.requests) == 1
    assert timer.sleeps == []
    assert events(caplog)[-1]["attempt_count"] == 1


@pytest.mark.parametrize("limit", [0, -1, 4, True, 1.5, "2", None])
def test_invalid_attempt_limits_rejected(limit):
    with pytest.raises(ValueError, match="max_attempts"):
        setup_service([], max_attempts=limit)


def test_output_limit_is_returned_without_retry(call, caplog):
    response = result(call).model_copy(update={"finish_reason": ModelFinishReason.OUTPUT_LIMIT})
    service, provider, timer = setup_service([response])
    assert service.generate(call) is response
    assert len(provider.requests) == 1
    assert timer.sleeps == []
    assert all(entry["outcome"] == "output_limit" for entry in events(caplog))


@pytest.mark.parametrize("is_error", [False, True])
def test_provider_context_mismatch_is_rejected_and_logs_original_context(call, caplog, is_error):
    wrong = call.context.model_copy(update={"operation_id": uuid4()})
    outcome = (
        ModelCallError(wrong, ModelErrorKind.TIMEOUT)
        if is_error
        else result(call).model_copy(update={"context": wrong})
    )
    service, provider, timer = setup_service([outcome])
    with pytest.raises(ModelCallError) as caught:
        service.generate(call)
    assert caught.value.context == call.context
    assert caught.value.kind == ModelErrorKind.INVALID_RESPONSE
    assert len(provider.requests) == 1
    assert timer.sleeps == []
    assert all(entry["operation_id"] == str(call.context.operation_id) for entry in events(caplog))


def test_unexpected_error_is_not_retried_or_logged_verbatim(call, caplog):
    failure = RuntimeError("SECRET unexpected error")
    service, provider, timer = setup_service([failure])
    with pytest.raises(RuntimeError) as caught:
        service.generate(call)
    assert caught.value is failure
    assert len(provider.requests) == 1
    assert timer.sleeps == []
    assert [entry["error_kind"] for entry in events(caplog)] == ["internal_error"] * 2
    assert "SECRET" not in caplog.text


def test_operations_do_not_share_attempt_state(call, caplog):
    second_call = call.model_copy(
        update={"context": call.context.model_copy(update={"operation_id": uuid4()})}
    )
    service, _, _ = setup_service([result(call), result(second_call)])
    service.generate(call)
    service.generate(second_call)
    operations = [entry for entry in events(caplog) if entry["event"] == "model_operation"]
    assert [entry["operation_id"] for entry in operations] == [
        str(call.context.operation_id),
        str(second_call.context.operation_id),
    ]
    assert all(entry["attempt_count"] == 1 for entry in operations)


def test_sdk_and_service_do_not_multiply_retries(call, caplog):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(503, json={"error": {"message": "SECRET upstream detail"}})

    with OpenAI(
        api_key="SECRET key", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    ) as client:
        service = ModelService(OpenAIProvider(client, call.context.model_id), sleep=lambda _: None)
        with pytest.raises(ModelCallError) as caught:
            service.generate(call)
    assert caught.value.kind == ModelErrorKind.UNAVAILABLE
    assert len(requests) == 3
    assert requests[0] == requests[1] == requests[2]
    assert len(events(caplog)) == 4
    assert "SECRET" not in caplog.text


def test_permanent_error_after_retry_stops_immediately(call, caplog):
    service, provider, timer = setup_service(
        [
            ModelCallError(call.context, ModelErrorKind.TIMEOUT),
            ModelCallError(call.context, ModelErrorKind.AUTHENTICATION),
        ]
    )
    with pytest.raises(ModelCallError) as caught:
        service.generate(call)
    assert caught.value.kind == ModelErrorKind.AUTHENTICATION
    assert len(provider.requests) == 2
    assert timer.sleeps == [0.5]
    assert events(caplog)[-1]["error_kind"] == "authentication"


def test_custom_two_attempt_limit(call, caplog):
    service, provider, timer = setup_service(
        [
            ModelCallError(call.context, ModelErrorKind.UNAVAILABLE),
            ModelCallError(call.context, ModelErrorKind.TIMEOUT),
        ],
        max_attempts=2,
    )
    with pytest.raises(ModelCallError) as caught:
        service.generate(call)
    assert caught.value.kind == ModelErrorKind.TIMEOUT
    assert len(provider.requests) == 2
    assert timer.sleeps == [0.5]
    assert events(caplog)[-1]["attempt_count"] == 2
