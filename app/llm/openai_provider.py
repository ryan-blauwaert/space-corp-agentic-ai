"""One text-only Responses API attempt, with SDK retries disabled."""

from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    omit,
)
from openai.types.responses import Response
from pydantic import ValidationError

from app.llm.contracts import (
    ModelFinishReason,
    ModelRequest,
    ModelResponse,
    ReasoningEffort,
    TokenUsage,
)
from app.llm.errors import ModelCallError, ModelErrorKind
from app.llm.provider import ModelProvider

_QUOTA_CODES = (
    "insufficient_quota",
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
)


class OpenAIProvider(ModelProvider):
    """The caller owns the injected client and must close it after use."""

    def __init__(
        self, client: OpenAI, model_id: str, reasoning_effort: ReasoningEffort | None = None
    ) -> None:
        self._client = client
        self.model_id = model_id
        self.reasoning_effort = reasoning_effort

    def generate(self, request: ModelRequest) -> ModelResponse:
        if request.context.model_id != self.model_id:
            raise ModelCallError(request.context, ModelErrorKind.INVALID_REQUEST)
        try:
            response = self._client.with_options(
                max_retries=0, timeout=request.timeout_seconds
            ).responses.create(
                model=self.model_id,
                input=request.prompt,
                max_output_tokens=request.max_output_tokens,
                store=False,
                reasoning={"effort": self.reasoning_effort}
                if self.reasoning_effort is not None
                else omit,
            )
        except APITimeoutError:
            raise ModelCallError(request.context, ModelErrorKind.TIMEOUT) from None
        except APIConnectionError:
            raise ModelCallError(request.context, ModelErrorKind.UNAVAILABLE) from None
        except APIStatusError as exc:
            status = exc.status_code
            if status in (401, 403):
                kind = ModelErrorKind.AUTHENTICATION
            elif status == 429:
                # Inspect structured identifiers only; never parse or forward messages.
                kind = (
                    ModelErrorKind.QUOTA_EXCEEDED
                    if exc.code in _QUOTA_CODES or exc.type == "insufficient_quota"
                    else ModelErrorKind.RATE_LIMIT
                )
            elif status == 408:
                kind = ModelErrorKind.TIMEOUT
            elif status == 409 or status >= 500:
                kind = ModelErrorKind.UNAVAILABLE
            else:
                kind = ModelErrorKind.INVALID_REQUEST
            raise ModelCallError(request.context, kind) from None
        except (APIResponseValidationError, ValueError):
            raise ModelCallError(request.context, ModelErrorKind.INVALID_RESPONSE) from None

        try:
            return self._normalize(response, request)
        except (AttributeError, TypeError, ValidationError):
            # SDK parsing is permissive; reject unusable shapes at our boundary.
            raise ModelCallError(request.context, ModelErrorKind.INVALID_RESPONSE) from None

    def _normalize(self, response: Response, request: ModelRequest) -> ModelResponse:
        if response.error is not None:
            kind = {
                "server_error": ModelErrorKind.UNAVAILABLE,
                "rate_limit_exceeded": ModelErrorKind.RATE_LIMIT,
                "invalid_prompt": ModelErrorKind.INVALID_REQUEST,
                "bio_policy": ModelErrorKind.REFUSED,
            }.get(response.error.code, ModelErrorKind.INVALID_RESPONSE)
            raise ModelCallError(request.context, kind)
        reason = response.incomplete_details.reason if response.incomplete_details else None
        if reason == "content_filter":
            raise ModelCallError(request.context, ModelErrorKind.REFUSED)
        if response.status == "completed" and reason is None:
            finish = ModelFinishReason.COMPLETED
        elif response.status == "incomplete" and reason == "max_output_tokens":
            finish = ModelFinishReason.OUTPUT_LIMIT
        else:
            raise ModelCallError(request.context, ModelErrorKind.INVALID_RESPONSE)
        parts: list[str] = []
        for item in response.output:
            if item.type == "reasoning":
                continue
            if item.type != "message" or item.role != "assistant":
                raise ModelCallError(request.context, ModelErrorKind.INVALID_RESPONSE)
            for content in item.content:
                if content.type == "refusal":
                    raise ModelCallError(request.context, ModelErrorKind.REFUSED)
                if content.type != "output_text":
                    raise ModelCallError(request.context, ModelErrorKind.INVALID_RESPONSE)
                parts.append(content.text)
        usage = response.usage
        return ModelResponse(
            context=request.context,
            text="".join(parts),
            finish_reason=finish,
            returned_model_id=response.model,
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            )
            if usage is not None
            else None,
        )
