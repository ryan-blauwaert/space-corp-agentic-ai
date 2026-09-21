"""The minimal model interface consumed by application services."""

from typing import Protocol

from app.llm.contracts import ModelRequest, ModelResponse


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Perform one bounded attempt, preserving context in its result or error.

        Implementations translate expected provider failures to ModelCallError.
        They honor the request's timeout/output bounds and do not independently
        retry. The application service owns retries and telemetry. No database,
        tool execution, streaming, or SDK-specific payload is part of this API.
        """
