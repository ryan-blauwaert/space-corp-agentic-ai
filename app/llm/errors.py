"""Stable failure categories without provider exception messages or payloads."""

from enum import StrEnum

from app.llm.contracts import ModelCallContext


class ModelErrorKind(StrEnum):
    AUTHENTICATION = "authentication"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXCEEDED = "quota_exceeded"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"
    REFUSED = "refused"


class ModelCallError(Exception):
    """Carry correlation and a safe category; retry policy belongs to the service."""

    def __init__(self, context: ModelCallContext, kind: ModelErrorKind) -> None:
        self.context = context
        self.kind = kind
        super().__init__(f"Model call failed: {kind.value}.")
