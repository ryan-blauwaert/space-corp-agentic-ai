# Controlled Model Integration

Waypoint 2.1 is being implemented incrementally. Units 1–3 define the boundary,
a configured OpenAI adapter, and controlled execution with telemetry. The smoke
command and live acceptance remain pending. Existing operational endpoints are unaffected.

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
both cases. The execution service owns retries and telemetry, so SDK retries must not
silently multiply application attempts. This interface includes no database access,
tool calling, streaming, or vendor-specific payloads.

`app/llm/errors.py` defines authentication, invalid-request, rate-limit, timeout,
unavailable, invalid-response, and refusal categories. Errors carry context and a
fixed safe message. The adapter maps SDK failures into these categories; the
execution service owns category-to-retry policy.

## Content handling

Prompt and response text are omitted from ordinary object representations, and
normalized error messages do not render context or provider exception text. This
is a precaution, not complete redaction: explicit serialization and Pydantic
validation errors can contain input. Contracts must not be logged wholesale.
Service telemetry selects approved metadata fields explicitly and excludes raw
prompts, outputs, credentials, and operational evidence.

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
The service decides which categories to retry. See the
[provider error guidance](https://developers.openai.com/api/docs/guides/error-codes).
Do not enable SDK debug logging for sensitive calls or log raw exceptions/payloads.

## Controlled execution and telemetry (unit 3)

`ModelService` accepts a `ModelProvider` and exposes `generate(request)`. Callers
use this service for controlled execution and own the provider's lifetime:

```python
with configured_provider(settings) as provider:
    service = ModelService(provider)
    response = service.generate(request)  # context.model_id must match configuration
```

The default is three attempts total, including the initial call. `max_attempts`
can be 1–3; 1 disables retries. Only rate limits, timeouts, and unavailable-service
failures are retried. Authentication, invalid requests/responses, and refusals stop
immediately. Partial text at the output limit is returned explicitly, without retry.
The same immutable request and correlation IDs are reused for every attempt.
Provider results/errors with mismatched context fail as invalid responses. Unexpected
programming exceptions are recorded as `internal_error` without exception details,
then re-raised rather than retried or disguised as provider failures.

Retries use exponential backoff with full jitter: 0–0.5 seconds before the second
attempt, 0–1 second before the third. This follows guidance to
[limit retries and use backoff with jitter](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_mitigate_interaction_failure_limit_retries.html).
For this initial integration the delays are deliberately short and fixed, and no
provider-specific retry-after hint crosses the interface. Sustained throttling ends
in a bounded failure. There is no queue or background retry mechanism.

Each attempt retains the request's timeout and output cap. Total runtime includes
all attempts and waits; the SDK timeout is not a strict operation deadline. Retrying
a timeout may duplicate provider processing and cost, even if the earlier response
was lost. This policy is for text generation without tool execution or application
writes, not a general retry policy for side-effecting actions.

The service emits JSON messages at INFO through `app.llm.service`, using standard
[Python logging](https://docs.python.org/3/library/logging.html). It does not install
handlers or change process-wide levels. The calling entry point must configure a
handler and enable INFO for this logger to collect events; ordinary Python's default
WARNING threshold hides them. The upcoming smoke command will provide that wiring.
No tracing service, persistence table, dependency, or API endpoint is added here.

One `model_attempt` event is emitted per finished attempt and one `model_operation`
event per finished call. Their allowlisted fields are:

| Fields | Meaning |
| --- | --- |
| `event` | Attempt or overall operation |
| `request_id`, `operation_id` | Caller-supplied correlation UUIDs |
| `model_id`, `prompt_id`, `prompt_version` | Configured model and application-managed prompt identity |
| `attempt_count` | Attempt ordinal, or total attempts for the operation |
| `duration_ms` | Monotonic elapsed time; operation duration includes waits |
| `outcome` | `completed`, `output_limit`, or `failed` |
| `error_kind` | Normalized category, `internal_error`, or null |
| `returned_model_id` | Provider-reported identifier on success, otherwise null |
| `input_tokens`, `output_tokens` | Reported counts for that response, otherwise null |

Operation usage repeats the final response's counts; it is not a sum across
attempts or a billing estimate. Consumers must not add attempt and operation counts
together. Failed attempts may consume unreported tokens. Unknown counts remain null.
The logging record supplies a wall-clock creation timestamp; durations use a
monotonic clock.

Only caller-supplied UUIDs and trusted model/prompt identifiers may be recorded from
request metadata. No raw prompts, generated text, credentials, operational evidence,
HTTP payloads, exception messages, or tracebacks are included. Identifiers must not
be populated with user content. This allowlist covers these service events, not
arbitrary logging by callers, SDKs, or exception handlers.

## Verification and remaining work

`tests/app/llm/` maps the provider-interface and predictable-failure criteria to
contract tests and actual SDK calls over a mocked HTTP transport. These cover
success/failure correlation, request bounds, disabled retries, missing/zero usage,
truncation, refusal, malformed responses, transport errors, model selection, and
client cleanup. Settings tests verify optional credentials and a configurable model.
Existing API tests continue to verify startup and operational routes without a key.
No model request is sent to the network by these tests.

`test_service.py` verifies bounded retries for each transient category, immediate
failure for permanent categories, eventual success and exhaustion, context integrity,
per-attempt/operation timing, truncation, allowlisted logs, and content exclusion on
success and failure. A mocked HTTP test combines the service and actual SDK adapter
to verify that retry counts do not multiply. Fake time avoids real waits in policy
tests. These cover the predictable-failure, identifier logging, correlation, and
telemetry-content criteria without claiming real-provider acceptance.

Remaining units add the smoke command and live acceptance. Real credentials, model
availability, live provider behavior, and entry-point log collection remain
unverified. Waypoint 2.1 remains incomplete. Query generation remains Waypoint 2.2
work.
