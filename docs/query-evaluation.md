# Query evaluation process

This process replaces tuning toward one perfect run of a repeatedly inspected suite.
It separates deterministic execution tests, development feedback, and a frozen model
assessment. No live calls were made while introducing it.

## Dataset roles

- `data/evaluations/queries-3.json` is the **development regression set**. Its questions
  and failures have informed prompt changes; it is not independent acceptance evidence.
- `data/evaluations/queries-holdout-1.json` is a **candidate wording holdout**: 24 new
  paraphrases with the same independently authored expected plans/evidence as the
  development set. It covers the 12 canonical scenarios, six additional combinations,
  and six declines. Prompt version 3 was frozen before authoring these questions.
  Their results have since informed general guardrail work: this set is now
  development evidence for version 4, despite its preserved historical purpose label.

The candidate holdout is deliberately labeled modestly: it was authored in this
repository with knowledge of the domain and development failures, not collected from
independent users. It tests new wording, not new business capabilities or a new data
distribution. It cannot support a production accuracy claim. Independent domain review
and genuinely new filter combinations should extend a later holdout before deployment.

Structural and database-oracle checks may inspect held-out questions to establish
validity. Do not add their questions, plans, or results to the model prompt. Once
holdout results influence prompt/model changes, that holdout becomes development
material; preserve it and author a new version for the next independent assessment.
Do not repeatedly edit a holdout while retaining its acceptance designation.

## Frozen pilot protocol

`data/evaluations/query-protocol-1.json` declares the following before collecting any
new live results:

- Configured model: `gpt-5.6-luna`; prompt: `bounded-query`, version `3`.
- Three runs of **each** dataset, 24 cases each: six reports, 144 logical model calls.
- One attempt per case, no repair or semantic retry loop. Existing 30-second per-attempt
  timeout, 4,096-token output cap, and application execution limits remain in place.
- Dataset, prompt/schema, and relevant implementation digests freeze the configuration.
  All returned model IDs must agree. An alias still cannot guarantee unchanged provider
  internals; use a supported fixed model revision in a later protocol when available.
- All planned results count. Do not stop on a good run, discard poor runs, substitute
  reruns, or mix reports from different configurations. Do not inspect holdout outcomes
  for tuning until the batch has completed.

These are provisional **synthetic pilot targets**, not industry benchmarks or a
production service-level objective. Each dataset must independently meet all targets:

| Outcome | Target across all three runs |
| --- | --- |
| Wrong query, wrong evidence, or execution of an expected decline | Zero occurrences |
| Execution/model errors or unclassified failures | Zero; investigate before accepting |
| Supported queries with correct intent and evidence | At least 95% (52 of 54) |
| Declines with the expected category and no evidence execution | At least 90% (17 of 18) |

This permits limited over-declining and decline-category mistakes, while treating
incorrect execution/evidence more strictly. A supported question failing in all three
runs does not meet the target. Thresholds are proposed for the next assessment, not
retroactively applied to earlier runs. Three repetitions only provide a small pilot
measurement; they do not establish statistical independence or high-confidence
production reliability. Report counts and per-case repeatability, not just percentages.

A live assessment needs explicit approval for its scope and cost. The existing
single-run approvals do **not** authorize this six-run protocol. Before starting,
record the approved six output paths and run order in a local batch ledger. Preserve
stdout and stderr for every slot under ignored `.local/`; never overwrite a failed
slot with another attempt. An interrupted batch is inconclusive; record the interruption
and obtain approval for any replacement protocol rather than quietly filling the gap.
The offline assessor cannot detect runs withheld from it or intentionally edited
reports; preservation of the ledger and all attempted runs is a process requirement.

## Offline assessment

The existing `scripts.evaluate_queries` command still runs one explicitly selected
dataset once. It does not automatically launch repetitions. Format-version-3 reports
add dataset purpose, prompt and implementation digests, and failure categories:

- `unexpected_execution`: a question expected to decline returned evidence.
- `wrong_query`: a supported question executed with incorrect intent.
- `wrong_evidence`: intent matched but evidence/execution outcome did not.
- `unnecessary_decline`: a supported question was declined.
- `decline_category`: the question declined with the wrong classification.
- `execution_error`: the model/application call failed; raw exception content is omitted.

After all approved slots finish, assess their reports locally:

```bash
.venv/bin/python -m scripts.assess_queries \
  .local/evaluations/dev-1.json .local/evaluations/dev-2.json .local/evaluations/dev-3.json \
  .local/evaluations/holdout-1.json .local/evaluations/holdout-2.json .local/evaluations/holdout-3.json
```

This command makes **no model or database calls**. It requires the complete six-report
batch, rejects duplicates, missing cases, configuration drift, old report formats,
inconsistent counts, and mixed model identities, then reports per-dataset rates,
per-case passes, and failure categories. Scoring normalizes membership order and
mathematically equivalent integer bounds (for example, quantity < 2 and quantity <= 1),
without accepting different thresholds or omitting filters. It does not average development and holdout
quality together. Exit 0 means the declared pilot quality targets were met; 1 means
measured targets were missed; 2 means the batch/configuration could not be assessed.

Report/dataset digests include the new purpose metadata. Earlier format-version-1/2
reports and their original digests remain historical development evidence; they cannot
be pooled into this protocol. Files and prompts are not retroactively relabeled.

## Waypoint acceptance and future work

Waypoint 2.2 completion requires both:

1. Deterministic tests of contracts, all supported filters/relationships, read-only
   access, workspace/pin boundaries, and safe failure handling pass without required
   checks skipped. The exact expected records remain tested independently of models.
2. The predeclared development/holdout assessment meets the documented pilot targets,
   with every result and any residual limitation recorded. A single perfect run cannot
   substitute for the batch. Any revision to targets must be explicit and precede a
   new assessment; do not choose thresholds after inspecting its results.

This distinction follows [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
on task-specific metrics, held-out evaluation, and continued measurement. Prompt
examples can still be useful development material; evaluation separation is what
prevents their success from being presented as evidence of generalization.

Later work can add independently reviewed questions, unfamiliar filter combinations,
real usage samples, latency/cost targets, and a larger repeated assessment. A future
interaction layer can clarify ambiguous references or provide typed-query fallback.
None of those features, model changes, or additional infrastructure are implemented
by this process update. The first assessment is recorded below; it did not meet the
declared targets, so Waypoint 2.2 remains in progress.


## Implementation verification

961 tests passed, no failures or skips, in 51.95 seconds, including PostgreSQL
verification of every candidate-holdout expectation with controlled model responses.
Tests cover report compatibility, incomplete/duplicate batches, mixed model identities,
configuration drift, per-dataset quality targets, critical-failure rejection, and
integer-bound equivalence without accepting off-by-one errors. Ruff lint/format,
mypy, and whitespace checks passed. One existing Starlette/AnyIO warning remains.
No live model accuracy or production reliability is claimed by these automated checks.

## First frozen assessment — 2026-09-21

The user explicitly authorized the full protocol. All six predeclared slots completed
from 19:24:12 to 19:28:41 UTC, with 144 model attempts and no retries or replacement
runs. The prompt, implementation, datasets, model configuration, and scoring rules
were unchanged during the batch. All reports passed the offline consistency checks;
the assessor exited **1** because the quality targets were not met.

Configuration: `query-protocol-1`, `bounded-query` version `3`, configured and returned
model `gpt-5.6-luna`. The immutable planned ledger, execution log, six JSON reports,
six JSONL traces, and offline assessment are under
`.local/evaluations/protocol-1-batch-1/`. The frozen fingerprints remain in the protocol
file. No historical results were substituted into this assessment.

| Metric | Development | Candidate wording holdout | Target per dataset |
| --- | --- | --- | --- |
| Supported queries | 52/54 (96.3%) | 34/54 (63.0%) | At least 95% |
| Correct declines | 18/18 (100%) | 18/18 (100%) | At least 90% |
| Unnecessary declines | 2 | 11 | Count against supported-query target |
| Resolution/call errors | 0 | 9 | Zero |
| Wrong query/evidence or unexpected execution reported | 0 | 0 | Zero |
| Assessment | Meets pilot targets | Does not meet pilot targets | Both must meet targets |

Individual run results, retained in planned order:

| Slot | Passed/24 | Run ID |
| --- | --- | --- |
| Development 1 | 24 | bf015ab5-88e5-45a5-a502-4cad4e055df7 |
| Development 2 | 23 | 34504bff-f97d-4bb3-a978-e26a160f84ee |
| Development 3 | 23 | 409f6818-6c28-421a-87fe-727e828044a1 |
| Holdout 1 | 18 | 7f7e2354-e571-4513-a5f3-5394cb0c6fa6 |
| Holdout 2 | 16 | 8a0d16a1-29d4-4ca6-9dc0-847a958a4cd3 |
| Holdout 3 | 18 | 5f28bb77-a360-4024-8ab2-a51044d25d5f |

### Observed failures and interpretation

Development's only failure was `completed-work`, incorrectly declined as ambiguous
in two of three runs. The holdout completed-work and facility-equipment-empty cases
were declined in all three runs. Holdout lunar low-stock failed twice, compatible
stock with no incident failed twice, and the zero/unknown-stock compatibility case
failed once. These total 11 unnecessary declines.

All three holdout recurrence questions failed in all three runs: the model selected
`incidents`, but reference resolution returned `not_found` before evidence execution.
These nine observations are recorded under `execution_error`, but the traces establish
resolution failures, not database outages or provider failures. The saved reports do
not preserve rejected reference values or their field assignments, so the exact
misresolution cannot be reconstructed.

There is a fixture-review concern: those recurrence questions say “on” followed by
a model UUID, without explicitly saying “model” after symbolic references are rendered.
A human author knows `@models:...` denotes a model, but the model sees only the UUID.
This may introduce ambiguity absent from the expected plan. It is a plausible contributor,
not a demonstrated diagnosis. Structural/oracle tests prove the records and expected
queries are valid; they do not prove the natural-language wording is unambiguous.
The original scores are retained without excluding or rewriting these cases after the fact.

The development/holdout gap shows the tuned-set score alone does not establish robust
handling of new wording. It does not isolate overfitting, model limitations, prompt
ambiguity, or fixture defects as the sole cause. All expected declines passed in this
batch, and no incorrect evidence execution was reported, but this finite synthetic
assessment cannot prove universal safety or production reliability.

### Follow-up, without more tuning during this assessment

1. Independently review failed holdout questions for explicit entity types and agreement
   with their expected intent. Preserve this batch unchanged; document any fixture defect.
2. Add safe failure diagnostics for the reference field/entity type involved in a
   resolution failure, rather than logging question text, IDs, or raw model output.
3. If these results inform prompt/model changes, treat this holdout as development
   material for that work and freeze a fresh reviewed holdout before the next assessment.
4. Compare any revised semantic guidance or model choice under the same predeclared
   protocol, with fresh explicit approval for live calls. Do not rerun unchanged cases
   until a passing selection appears.

At the end of this assessment, only documentation was updated; its 961-test verification
and frozen reports describe that historical implementation. Subsequent work is below.


## Subsequent guardrail revision — prompt version 4

General changes add bounded, scoped type grounding for literal UUIDs before planning
and replace the accumulated prompt clarifications with capability descriptions and
ordered decision rules. No question-specific dispatch, extra model call, dependency,
fixture edit, threshold change, or automatic semantic repair was introduced. See the
[query guide](structured-queries.md#general-capability-guidance-prompt-version-4) for
behavior, tests, and limits. Identity hints add only entity types to identifiers already
supplied by the caller; future live-call approval must include this context.

Verification: 968 tests passed, including required PostgreSQL integration tests, with
no failures or skips. Ruff, formatting, mypy, and whitespace checks passed; one existing
Starlette/AnyIO deprecation warning remains. No live calls were made for this revision.
A deterministic passing suite proves the
application behavior, not improved model accuracy. Preserve `query-protocol-1` and
all six original reports. The offline assessor will intentionally reject that protocol
against changed source fingerprints; its saved assessment remains the historical result.
Do not update its hashes to make it match new code. Define a new frozen protocol and
fresh independently reviewed holdout before the next independent assessment. The old
holdout can still be used as development regression data, not new acceptance evidence.
Waypoint 2.2 remains in progress.
