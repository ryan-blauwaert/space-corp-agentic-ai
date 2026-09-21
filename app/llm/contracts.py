"""Validated values crossing the application/provider boundary."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NonblankText = Annotated[str, Field(min_length=1, pattern=r"\S")]
TokenCount = Annotated[int, Field(ge=0, strict=True)]


class ModelCallContext(BaseModel):
    """Caller-owned identity, preserved across attempts, results, and failures.

    One request can contain several operations. Retries keep the same operation
    ID; a separate logical model call receives a new operation ID. Identifiers
    describe configuration and must never contain prompt text or credentials.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: UUID
    operation_id: UUID
    model_id: NonblankText
    prompt_id: NonblankText
    prompt_version: NonblankText


class ModelRequest(BaseModel):
    """One text-generation attempt with explicit time and output bounds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    context: ModelCallContext
    prompt: NonblankText = Field(repr=False)
    max_output_tokens: int = Field(gt=0, strict=True)
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)


class TokenUsage(BaseModel):
    """Provider-reported counts: unknown is None, not zero or an estimate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: TokenCount | None = None
    output_tokens: TokenCount | None = None


class ModelFinishReason(StrEnum):
    COMPLETED = "completed"
    OUTPUT_LIMIT = "output_limit"


class ModelResponse(BaseModel):
    """Normalized text result, including an explicit incomplete-output outcome.

    The adapter must preserve the request context. returned_model_id records the
    provider's model identifier when supplied; it does not imply that an alias is
    a reproducible model snapshot. A refusal or unusable response is an error.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    context: ModelCallContext
    text: NonblankText = Field(repr=False)
    finish_reason: ModelFinishReason
    returned_model_id: NonblankText | None = None
    usage: TokenUsage | None = None
