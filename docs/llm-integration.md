# Controlled Model Integration

Waypoint 2.1 is being implemented incrementally. The first unit defines the boundary
only; no provider, credentials, model call, retry loop, or telemetry emission is
implemented yet. Existing operational endpoints are unaffected.

## Contracts

`app/llm/contracts.py` uses the project's existing Pydantic dependency for frozen,
validated request/response values. Unknown fields are rejected.

- `ModelCallContext` contains caller-supplied request and operation UUIDs, a
  requested model identifier, and a prompt identifier/version. Several operations
  can belong to one request. A retry retains the same operation ID; a new logical
  call receives a new one. This is correlation metadata, not an authorization scope.
- `ModelRequest` contains that context, a nonblank text prompt, a positive output
  token limit, and a positive finite per-attempt timeout. Enforcing those bounds
  is the future adapter's responsibility; constructing a request performs no I/O.
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
fixed safe message. Category-to-retry policy and SDK error mapping belong to later
units; this commit does not claim to handle real provider failures yet.

## Content handling

Prompt and response text are omitted from ordinary object representations, and
normalized error messages do not render context or provider exception text. This
is a precaution, not complete redaction: explicit serialization and Pydantic
validation errors can contain input. Contracts must not be logged wholesale.
Later telemetry must select approved metadata fields explicitly and exclude raw
prompts, outputs, credentials, and operational evidence by default.

## Verification and remaining work

`tests/app/llm/` covers valid/invalid contracts, immutable values, unknown versus
zero usage, incomplete output, safe error messages, and fake-provider success and
failure correlation. These tests require no provider SDK, keys, or network access.

Remaining units add one configured provider, controlled execution with telemetry,
a smoke command, and live acceptance. Waypoint 2.1 remains incomplete until those
requirements are verified. Query generation remains Waypoint 2.2 work.
