# Controlled Model Integration

Waypoint 2.1 is complete. Units 1–4 provide the boundary,
a configured OpenAI adapter, controlled execution with telemetry, and an internal
smoke command. Live acceptance evidence is recorded below. Existing operational
endpoints are unaffected.

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

`app/llm/errors.py` defines authentication, invalid-request, rate-limit, quota-exceeded, timeout,
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
failures are retried. Quota failures, authentication, invalid requests/responses, and refusals stop
immediately. Partial text at the output limit is returned explicitly, without retry.
The same immutable request and correlation IDs are reused for every attempt.
For HTTP 429, the adapter recognizes `insufficient_quota`,
`credit_balance_exhausted`, `organization_spend_limit_exceeded`,
`project_spend_limit_exceeded`, and `organization_usage_limit_exceeded` codes, or
an `insufficient_quota` type. These map to `quota_exceeded`, which is not retried.
Check API credits and organization/project limits before trying again. Other 429s
retain `rate_limit`, including unknown/missing identifiers; retries stay bounded.
Classification uses structured identifiers only, never provider message text.
This follows the [OpenAI error guidance](https://developers.openai.com/api/docs/guides/error-codes).

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
WARNING threshold hides them. The smoke command below provides that wiring.
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

## Internal smoke command (unit 4)

From the repository root, configure `SPACE_CORP_LLM_MODEL_ID` and
`SPACE_CORP_LLM_API_KEY` in your environment or ignored `.env` file. No model is
selected automatically; use an available Responses-compatible text model. Do not
put keys in command arguments or tracked files. The command needs no database or
workspace and does not import the API application.

```bash
.venv/bin/python -m scripts.smoke_llm
```

This command makes a real provider call when credentials are configured and can
incur provider charges. It sends only the fixed prompt “Reply with the single word
READY. Do not use tools.”, identified by `model-smoke` version `1`. It creates new
request and operation UUIDs, invokes the existing provider through `ModelService`,
and closes the client on success or failure. No operational data, tools, or database
writes are involved. Changes to the fixed prompt require a prompt-version change.

Defaults are a 256-token output cap, a 30-second per-attempt SDK timeout, and at
most three attempts. Override bounds explicitly when needed:

```bash
.venv/bin/python -m scripts.smoke_llm --max-output-tokens 512 --timeout-seconds 20 --max-attempts 1
```

The output cap includes reasoning tokens for applicable models; a low cap may
produce no usable text or an output-limit response. Retry and timeout semantics
are those of the service described above. `--help` performs no model call and
requires no configuration.

Stdout contains one JSON result summary with `request_id`, `operation_id`,
`outcome`, and `error_kind`. Stderr contains the allowlisted JSON attempt/operation
events. The command explicitly enables INFO for the service logger, independent
of `SPACE_CORP_LOGGING_LEVEL`, and does not enable verbose SDK logging. It restores
service logging state on exit. Neither output stream prints the prompt, generated
text, key, exception details, or traceback. Disable externally configured SDK debug
logging when working with credentials, as described above.

| Exit code | Meaning |
| --- | --- |
| `0` | Provider returned usable, completed text |
| `1` | Model/setup failure or output-limit partial text |
| `2` | Invalid arguments, invalid settings, or missing model/key |

Success verifies the text-call path, not exact compliance with the requested word
or answer quality. Output-limit text is not counted as a successful smoke check.
Configuration failures occur before a call and print a safe diagnostic to stderr;
they have no result summary or model events. Setup failures produce a safe summary,
but no model events if execution never began. Model failures retain the same IDs in
the summary and telemetry, including across retries.

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

`tests/scripts/test_smoke_llm.py` runs the command through the real adapter/service
with mocked HTTP to verify entry-point wiring, emitted console telemetry, correlation,
retry bounds, exit codes, validation, cleanup, and sensitive-content exclusion.
A subprocess test verifies module invocation without model or database settings.
Tests send no live model requests.

Quota regression tests cover each recognized billing/quota code, the type fallback,
unknown/malformed identifiers, and transient throttling. Command tests prove that
quota failures emit safe, correlated events and stop after one HTTP attempt despite
the default three-attempt allowance.

## Live acceptance (unit 5)

The following evidence was supplied by the user from local smoke-command runs.
These were live calls, separate from the mocked automated suite. No additional
provider calls were made to record this evidence.

| Run | Requested / returned model | Result | Attempts | Operation duration | Reported input / output tokens |
| --- | --- | --- | --- | --- | --- |
| Initial failure | `gpt-5-nano` / null | `rate_limit` under the original mapping | 3 | 4323.542 ms | unknown / unknown |
| Nano success | `gpt-5-nano` / `gpt-5-nano-2025-08-07` | completed | 1 | 1641.14 ms | 18 / 109 |
| Luna success | `gpt-5.6-luna` / `gpt-5.6-luna` | completed | 1 | 2458.105 ms | 18 / 5 |

Correlation evidence (each pair is shared by every attempt, operation event, and
command summary in that run):

| Run | Request ID | Operation ID |
| --- | --- | --- |
| Initial failure | `9b220d53-91ba-4197-9139-0c7e17df4497` | `97d7735b-fe30-4820-84e3-15cdc3c853a3` |
| Nano success | `f0c74776-ec7b-4e12-8d71-18b13156768b` | `2f31dc66-fcab-4549-9ad3-f2994982686e` |
| Luna success | `b0c81943-dde9-46ba-928e-006ee5be83fa` | `3f15378a-1a3f-4841-a835-6456d355c200` |

All runs record prompt `model-smoke`, version `1`, and exclude raw prompt/output,
credentials, and evidence content. Success summaries report `completed` with null
error categories. The earlier failure demonstrates bounded retries and failure
correlation, but does not reveal its original provider code; it cannot be
retroactively classified as quota exhaustion. The corrected quota distinction is
verified with mocked HTTP responses, not an intentionally induced live billing
failure. Returned aliases are not proof of an immutable model revision.

### Completion evidence and limits

- Model invocation: user-supplied live successes above, plus command wiring tests.
- Provider interface: explicit `ModelProvider` implementation checked by mypy.
- Predictable failures: adapter, service, and command tests; live bounded-failure trace.
- Model/prompt identity and correlation: automated assertions and all three live traces.
- Content handling: explicit telemetry allowlist, safe console output tests, and the
  documented metadata policy above.

Final verification: 526 automated tests passed with no failures or skips; Ruff
and mypy passed. One existing Starlette/AnyIO deprecation warning remains.

This verifies the Waypoint 2.1 integration criteria, not model answer quality or
performance across workloads. Automated tests remain independent of credentials
and network access. No live quota failure was induced, and arbitrary third-party
logging is outside the service telemetry guarantee. Waypoint 2.2 now defines
[bounded domain query contracts and fixtures](structured-queries.md). Units 3–4
execute all five domains; unit 5 connects `ModelService` through `QueryService.ask()`
to strict JSON validation, exact entity resolution, and execution. Its versioned
`bounded-query` prompt selects a domain and combines approved typed filters; Q1–Q5
remain examples. It uses the existing text-only provider with application-side
validation, not provider-native Structured Outputs or tool calling. The repeatable
live evaluation journey remains unit 6 work.
The existing provider/service boundary remains responsible for model calls; query
validation, workspace authority, and execution controls remain application-owned.
