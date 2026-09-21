"""Bounded model execution and content-free operation/attempt telemetry."""

import json
import logging
import random
import time
from collections.abc import Callable
from typing import Literal

from app.llm.contracts import ModelRequest, ModelResponse
from app.llm.errors import ModelCallError, ModelErrorKind
from app.llm.provider import ModelProvider

logger = logging.getLogger(__name__)
_RETRYABLE = frozenset(
    {ModelErrorKind.RATE_LIMIT, ModelErrorKind.TIMEOUT, ModelErrorKind.UNAVAILABLE}
)


class ModelService:
    """Execute text-only calls; the caller owns the provider's lifetime.

    Limits count attempts, including the initial call. Request timeouts apply to
    each attempt, not an end-to-end deadline. No SDK retry loop may be enabled.
    """

    def __init__(
        self,
        provider: ModelProvider,
        *,
        max_attempts: int = 3,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be an integer between 1 and 3.")
        self._provider = provider
        self._max_attempts = max_attempts
        self._clock = clock
        self._sleep = sleep
        self._uniform = uniform

    def generate(self, request: ModelRequest) -> ModelResponse:
        operation_start = self._clock()
        attempt = 0
        try:
            for attempt in range(1, self._max_attempts + 1):
                attempt_start = self._clock()
                try:
                    response = self._provider.generate(request)
                    if response.context != request.context:
                        raise ModelCallError(request.context, ModelErrorKind.INVALID_RESPONSE)
                except ModelCallError as error:
                    if error.context != request.context:
                        error = ModelCallError(request.context, ModelErrorKind.INVALID_RESPONSE)
                    self._record(
                        request, "model_attempt", attempt_start, attempt, error_kind=error.kind
                    )
                    if error.kind not in _RETRYABLE or attempt == self._max_attempts:
                        raise error from None
                    # Full jitter: first retry waits 0–0.5s, second waits 0–1s.
                    self._sleep(self._uniform(0.0, 0.5 * 2 ** (attempt - 1)))
                except Exception:
                    self._record(
                        request,
                        "model_attempt",
                        attempt_start,
                        attempt,
                        error_kind="internal_error",
                    )
                    raise
                else:
                    self._record(
                        request, "model_attempt", attempt_start, attempt, response=response
                    )
                    self._record(
                        request, "model_operation", operation_start, attempt, response=response
                    )
                    return response
        except ModelCallError as error:
            self._record(
                request, "model_operation", operation_start, attempt, error_kind=error.kind
            )
            raise
        except Exception:
            # Record no exception text or traceback; preserve programming errors for callers.
            self._record(
                request, "model_operation", operation_start, attempt, error_kind="internal_error"
            )
            raise
        raise AssertionError("Validated attempt limit must produce a result or failure.")

    def _record(
        self,
        request: ModelRequest,
        event: Literal["model_attempt", "model_operation"],
        started_at: float,
        attempt: int,
        *,
        response: ModelResponse | None = None,
        error_kind: ModelErrorKind | Literal["internal_error"] | None = None,
    ) -> None:
        context = request.context
        usage = response.usage if response is not None else None
        # Explicit allowlist: never serialize a request, response, or exception wholesale.
        logger.info(
            json.dumps(
                {
                    "event": event,
                    "request_id": str(context.request_id),
                    "operation_id": str(context.operation_id),
                    "model_id": context.model_id,
                    "prompt_id": context.prompt_id,
                    "prompt_version": context.prompt_version,
                    "attempt_count": attempt,
                    "duration_ms": round((self._clock() - started_at) * 1000, 3),
                    "outcome": response.finish_reason.value if response is not None else "failed",
                    "error_kind": error_kind,
                    "returned_model_id": response.returned_model_id
                    if response is not None
                    else None,
                    "input_tokens": usage.input_tokens if usage is not None else None,
                    "output_tokens": usage.output_tokens if usage is not None else None,
                },
                separators=(",", ":"),
            )
        )
