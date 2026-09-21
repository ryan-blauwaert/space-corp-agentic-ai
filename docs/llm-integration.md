# Controlled Model Integration

Waypoint 2.1 is being implemented incrementally. Units 1–2 define the boundary
and a configured OpenAI adapter. Retry orchestration, telemetry emission, and
live acceptance remain pending. Existing operational endpoints are unaffected.

## Contracts

`app/llm/contracts.py` uses the project's existing Pydantic dependency for frozen,
validated request/response values. Unknown fields are rejected.

- `ModelCallContext` contains caller-supplied request and operation UUIDs, a
  requested model identifier, and a prompt identifier/version. Several operations
  can belong to one request. A retry retains the same operation ID; a new logical
  call receives a new one. This is correlation metadata, not an authorization scope.
- `ModelRequest` contains that context, a nonblank text prompt, a positive output
  token limit, and a positive finite per-attempt timeout. Enforcing those bounds
  is the adapter's responsibility; constructing a request performs no I/O.
- `ModelResponse` preserves context and contains nonblank text, a completion reason,
  optional provider-reported model identifier, and optional usage. An output-limit
  result is explicitly incomplete, not silently classified as completed.
- `TokenUsage` holds nonnegative integer input/output counts when available.
  Unknown counts remain null; zero means a known zero. No counts are estimated.

The requested model identifier may be an alias or a pinned version. The returned
identifier records what the provider reports and is not assumed to establish
reproducibility. Prompt identifiers/versions must refer to application-managed
prompt definitions; they must not embed user content or credentials.

`app/llm/provider.py` declares the synchronous `ModelProvider.generate` protocol.
An implementation performs one bounded attempt and returns `ModelResponse` or
raises `ModelCallError` for an expected provider failure. It preserves context in
both cases. The future service owns retries and telemetry, so SDK retries must not
silently multiply application attempts. This interface includes no database access,
tool calling, streaming, or vendor-specific payloads.

`app/llm/errors.py` defines authentication, invalid-request, rate-limit, timeout,
unavailable, invalid-response, and refusal categories. Errors carry context and a
fixed safe message. The adapter maps SDK failures into these categories; category-to-retry policy
belongs to the future execution service.

## Content handling

Prompt and response text are omitted from ordinary object representations, and
normalized error messages do not render context or provider exception text. This
is a precaution, not complete redaction: explicit serialization and Pydantic
validation errors can contain input. Contracts must not be logged wholesale.
Later telemetry must select approved metadata fields explicitly and exclude raw
prompts, outputs, credentials, and operational evidence by default.

## Configured provider (unit 2)

The first implementation uses the OpenAI Python SDK and Responses API, behind
`ModelProvider`. The SDK dependency owns HTTP serialization and response parsing;
no orchestration framework or additional infrastructure is introduced.

Set `SPACE_CORP_LLM_MODEL_ID` and `SPACE_CORP_LLM_API_KEY` locally when model calls
are needed. There is no default model. Choose a model available to your account
that supports text input/output through Responses. Changing providers still
requires another adapter; this unit makes the model configurable, not arbitrary
provider protocols. Existing API startup requires neither setting.

`configured_provider(settings)` is a context manager that validates those settings
and closes its SDK client on exit. It does not call the model. Its yielded adapter
exposes the configured model identifier for constructing request context. A request
with a different identifier fails before network I/O. Credentials are explicit and
the API origin is fixed, rather than inheriting `OPENAI_BASE_URL`. Injected clients
used directly with `OpenAIProvider` remain their caller's responsibility.

Each call sends the request's output cap and timeout, disables SDK retries, and
sets `store=False`. The timeout applies to SDK network operations, not a strict
end-to-end wall-clock deadline. The output cap includes reasoning tokens where
applicable. `store=False` is not a claim of zero provider retention. See the
[SDK configuration reference](https://developers.openai.com/api/reference/python)
and [Responses API reference](https://developers.openai.com/api/reference/python/resources/responses/methods/create).

Completed text and output-limit partial text normalize to the existing contract.
Refusals, empty/malformed results, unexpected tool outputs, and unsupported response
states fail explicitly. Reasoning items are ignored; no tools execute. Unknown usage
counts stay null. Authentication, invalid requests, throttling, timeouts, and service
failures map to stable categories without displaying provider exception messages.
The service will decide which categories to retry. See the
[provider error guidance](https://developers.openai.com/api/docs/guides/error-codes).
Do not enable SDK debug logging for sensitive calls or log raw exceptions/payloads.

## Verification and remaining work

`tests/app/llm/` maps the provider-interface and predictable-failure criteria to
contract tests and actual SDK calls over a mocked HTTP transport. These cover
success/failure correlation, request bounds, disabled retries, missing/zero usage,
truncation, refusal, malformed responses, transport errors, model selection, and
client cleanup. Settings tests verify optional credentials and a configurable model.
Existing API tests continue to verify startup and operational routes without a key.
No model request is sent to the network by these tests.

Remaining units add controlled execution with telemetry, a smoke command, and live
acceptance. Real credentials, model availability, and provider behavior have not
been verified. Telemetry and retry-policy criteria remain uncovered until their
implementation units. Waypoint 2.1 remains incomplete. Query generation remains
Waypoint 2.2 work.
