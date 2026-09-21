# Query evaluation process

This process replaces tuning toward one perfect run of a repeatedly inspected suite.
It separates deterministic execution tests, development feedback, and a frozen model
assessment. No live calls were made while introducing it.

## Current model configuration

Use `gpt-5.6-luna` with `medium` reasoning for bounded queries and evaluations.
These are the defaults in `.env.example` and the validated configuration for the final
Waypoint 2.2 assessment. The provider remains configurable through
`SPACE_CORP_LLM_MODEL_ID` and `SPACE_CORP_LLM_REASONING_EFFORT`; shell environment
values override `.env`. Changing models is a deliberate configuration decision, not
an automatic fallback. Live calls still require explicit approval.

GPT-5.2 was tested during earlier troubleshooting and carried into the prepared
`query-protocol-2.json`; it is not the project default. Frozen protocols retain their
original configuration. For the completed Luna assessment, explicitly pass
`--protocol data/evaluations/query-protocol-2-luna.json` to the offline assessor;
its legacy default still points to the historical first protocol.

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
declared targets, so Waypoint 2.2 remained in progress at that point.


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
Waypoint 2.2 remained in progress at that point.

## Authorized iterative regression — prompt version 5

The user authorized up to ten holdout runs, followed by a joint development/holdout
check. All runs use the configured `gpt-5.6-luna`, one attempt per question, unchanged
fixture questions and expectations. Reports and per-run ledgers are preserved under
`.local/evaluations/guardrail-iteration-20260921/`. The final holdout check counts
inside the ten-run ceiling. This is iterative regression work on inspected datasets,
not a new independent acceptance protocol.

The planner's descriptions now include returned evidence for every domain, exact
fault-code semantics, and exactly representable integer restrictions. A deterministic
literal-fault-code check rejects invented values. Reports additionally retain resolved
`actual_plan` values for diagnosis; those values are excluded from routine event logs.
Reports should remain in ignored local storage. No raw model responses are logged.

The first run scored 23/24. Its sole mismatch explicitly selected every incident
status and severity instead of leaving those dimensions unrestricted; returned evidence
matched. The original report is preserved. The evaluator now recognizes full enum
selection on non-null row attributes as equivalent to no restriction, with deterministic
and database tests. Subsets remain distinct, and relationship-existence predicates are
never erased. This changes semantic comparison, not fixtures or acceptance thresholds.

Prompt version 6 additionally describes existing quantity operators mathematically and
clarifies facility-type selection in the contracts. Both Luna revisions still sometimes
declined a representable quantity request, so further prompt tuning stopped. GPT-5.2
with its default reasoning setting scored 22/24; simply changing models was insufficient.
A configurable `SPACE_CORP_LLM_REASONING_EFFORT` was then added to the existing provider
and recorded in reports. GPT-5.2 with `medium` scored 24/24 on its first holdout run;
the paired check below evaluates that exact setting without further prompt edits.

The first GPT-5.2 medium paired check scored 23/24 development and 24/24 holdout.
Development exposed an unsafe selection of one of two candidate units. This led to a
general application-owned ambiguity check: executable plans with multiple distinct
visible UUID candidates of the same entity kind now decline rather than silently
choose or drop candidates. Tests cover all five entity kinds, duplicate spellings,
different kinds, and retention of existing prohibited-operation declines. The query
guide records its conservative behavior and names/codes coverage limitation.


### Final recorded outcome

All ten authorized holdout runs were used, including paired checks; four development
runs were also performed. All 14 reports were retained: 336 model attempts, exactly
one per question, no retries. Neither fixtures nor expected evidence were edited.
The raw per-run sequence follows; scores from different configurations are not pooled
into an accuracy claim.

| Run | Dataset | Model / reasoning | Prompt | Score |
| --- | --- | --- | --- | --- |
| 1 | holdout | gpt-5.6-luna / default | 5 | 23/24 |
| 2 | holdout | gpt-5.6-luna / default | 5 | 24/24 |
| 3 | development | gpt-5.6-luna / default | 5 | 24/24 |
| 4 | holdout | gpt-5.6-luna / default | 5 | 23/24 |
| 5 | holdout | gpt-5.6-luna / default | 6 | 24/24 |
| 6 | development | gpt-5.6-luna / default | 6 | 24/24 |
| 7 | holdout | gpt-5.6-luna / default | 6 | 23/24 |
| 8 | holdout | gpt-5.2 / default | 6 | 22/24 |
| 9 | holdout | gpt-5.2 / medium | 6 | 24/24 |
| 10 | development | gpt-5.2 / medium | 6 | 23/24 |
| 11 | holdout | gpt-5.2 / medium | 6 | 24/24 |
| 12 | holdout | gpt-5.2 / medium | 6 | 24/24 |
| 13 | development | gpt-5.2 / medium | 6 | 23/24 |
| 14 | holdout | gpt-5.2 / medium | 6 | 24/24 |

Run 1's original mismatch was the semantically equivalent full-enum selection;
its score was not overwritten. The evaluator correction applies starting with run 2.
The final implementation (runs 12–14) passed holdout twice (24/24 each), but its final
development run scored **23/24**: `missing-facility` produced an unrestricted inventory
query instead of declining. It returned records for a broader scope than the user
specified. This is an **unexpected execution**, not just a decline-category issue.
The final paired result is therefore **47/48, not a successful resolution**.

The multiple-UUID ambiguity guard addresses silent candidate selection, but does not
prove preservation of a scope that has no identifiable reference. Literal fault checks
also cannot prove that every requested filter was included. Passing controlled tests
is not evidence that the model always interprets these requests correctly.

Verification: **996 tests passed**, including required PostgreSQL integration tests,
with no failures or skips. Ruff, formatting, mypy, and whitespace checks passed. One
existing Starlette/AnyIO deprecation warning remains. No commits were created, no
saved model setting was changed, and the ten-run authorization is exhausted.

At this point Waypoint 2.2 remained in progress. Further work needed to address scope explicitly at the
caller/contract boundary, so unresolved scope cannot silently become unrestricted
execution, rather than accumulating phrase-specific prompt rules. That design and its
coverage of legitimate workspace-wide queries need review before implementation. A
new independent assessment still requires a fresh reviewed holdout and authorization;
these inspected sets remain development regression material. Do not select only the
passing runs or weaken the zero-unexpected-execution criterion.


## Final scope-boundary assessment preparation

The scope-confirmation boundary is now implemented and covered by controlled tests.
It changes execution behavior without introducing new query capabilities: unanchored
plans cannot produce evidence until the caller confirms the complete resolved plan.
The evaluator simulates that review locally after planning and still scores incorrect
proposals as failures. Model interpretation is not presumed correct because review
prevented execution. Existing evidence and safety criteria are unchanged.

`query-protocol-2.json` freezes the final source/prompt fingerprints, GPT-5.2 snapshot
`gpt-5.2-2025-12-11`, medium reasoning, and `scope_confirmation` execution mode. It
requires three runs each of `queries-3` and fresh `queries-holdout-2` (144 single-attempt
calls). The same 95% supported-query, 90% decline-classification, and zero critical-error
targets apply. Older automatic-execution reports cannot be mixed with this protocol.

The new candidate holdout changes wording while retaining the independently authored
expected plans/evidence. It was authored after the implementation was fixed and checked against the contracts
and database oracle before any live calls.
It is synthetic wording coverage authored with domain knowledge, not an independently
collected user corpus. At preparation, user review and live-run approval were pending. No claim of
production generalization or perfect interpretation follows from passing this pilot.

The readable review copy is `.local/evaluations/scope-holdout-review.md`; the JSON
fixture is authoritative. The prepared local runner is
`.local/evaluations/run_scope_batch.py`, with immutable planned outputs under
`.local/evaluations/protocol-2-batch-1/`. It runs all six slots once, retains failures,
and assesses the complete batch; it never selects or replaces a favorable run.

The prior ten-run permission was exhausted. The prepared batch required fresh approval;
the user subsequently selected Luna, as recorded below. The GPT-5.2 batch remains unrun.
Preserve every result and the documented review requirement; do not start another tuning
loop or weaken thresholds implicitly.

Final local verification for this revision: **1,021 tests passed**, no failures or skips,
including the fresh fixture's restricted-database oracle checks. Lint, formatting, types,
and whitespace checks passed. One existing Starlette/AnyIO warning remains.


## Luna final assessment — 2026-09-21

The user authorized running the assessment first with `gpt-5.6-luna`. Separate frozen
`data/evaluations/query-protocol-2-luna.json` changes only the protocol identifier and
model from the prepared GPT-5.2 protocol. Medium reasoning, prompt 6, source/dataset
fingerprints, scope-confirmation mode, repetitions, and thresholds remain unchanged.
The GPT-5.2 batch was not run. No prompt, implementation, or fixture edits were made
during the Luna batch; no runs were replaced or selected after viewing scores.

| Dataset | Run 1 | Run 2 | Run 3 | Supported | Declines |
| --- | --- | --- | --- | --- | --- |
| Development (`queries-3`) | 24/24 | 24/24 | 24/24 | 54/54 | 18/18 |
| Fresh wording holdout (`queries-holdout-2`) | 24/24 | 24/24 | 24/24 | 54/54 | 18/18 |

**The frozen assessment passed, closing Waypoint 2.2 for the guarded workflow.**
Both datasets exceeded the 95% supported-query and 90% decline-classification targets,
with zero incorrect queries, evidence mismatches, unexpected executions, execution
errors, or unclassified failures. All 144 model calls completed in one attempt and
returned `gpt-5.6-luna`. An initial runner import error occurred before any model calls;
correcting the local import path did not consume or replace a scored run.

Thirty cases required exact-plan confirmation, simulated by the evaluator only after
the proposed plan matched the expected plan. The remaining 114 cases did not require
confirmation (including declines). This validates the reviewed workflow, not autonomous
interpretation. Production callers must supply real review or clarification and must
not automatically approve broad plans. The holdout is synthetic wording coverage of
existing intents, not an independent real-user corpus; anchored plans can still omit
filters, and future model outputs can fail despite this passing batch. Broader independent
user coverage and review usability remain future validation work, without changing the
current query capabilities or claiming production readiness.

The ignored local evidence directory is `.local/evaluations/protocol-2-luna-batch-1/`:
`ledger.json` freezes six slots, `events.jsonl` records exits, six JSON reports and six
trace files retain all observations, and `assessment.json` records the passing offline
assessment. The committed protocol identifies exact source, prompt, and dataset hashes.
Earlier failed reports and protocols remain intact. The batch permission is exhausted;
any further live run needs fresh approval. No commits or saved model-setting changes
were made. The preceding 1,021-test verification applies to this unchanged implementation;
this assessment added only a protocol and documentation updates.
