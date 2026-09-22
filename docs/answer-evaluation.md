# Answer evaluation

Waypoint 2.3 now has repeatable fixed-evidence and live end-to-end answer evaluation,
plus an offline assessor for report-bound factual assessments. Acceptance follows the
roadmap: evaluate grounding, cautious behavior, coverage, and tracing against expected
evidence. No live calls are authorized by this document.

## Inputs and correction

`answers-1.json` supplies required facts and prohibited claims for all 24 `queries-3`
cases. Its two mistaken references to a specified unit in the model-scoped recurrence
examples were corrected in place at the user's direction. No query, expected record,
or acceptance threshold changed. The loader verifies exact case coverage, purpose,
dataset digest, and agreement between expected answer state and query evidence.

`queries-holdout-3.json` and `answers-holdout-1.json` contain 24 fresh wordings with the
same expected plans and evidence. They were authored after the planner and renderer
were fixed, without live feedback. They are candidate synthetic wording coverage,
not independent real-user data or new filter combinations. Review their wording before
live acceptance. No question text, expected fact, or prohibited claim is added to a prompt.
The old query assessment records remain unchanged.

## Fixed-evidence evaluation

```bash
.venv/bin/python -m scripts.evaluate_answers \
  --output .local/evaluations/answers-fixed-development

.venv/bin/python -m scripts.evaluate_answers \
  --dataset data/evaluations/queries-holdout-3.json \
  --answers data/evaluations/answers-holdout-1.json \
  --output .local/evaluations/answers-fixed-holdout
```

Without `--live`, the command uses authored expected query results and deterministic
rendering. It opens no database connection, constructs no provider, and makes no model
calls. Scope is marked confirmed in the synthetic input when required; this does not
measure actual confirmation or planning. Fixed-evidence trace checks are not applicable.

Each exclusive output directory contains:

- `run.json`: run identity, mode, planned case keys, model configuration, and source hash.
- `cases.jsonl`: each case saved as it finishes, including traces and delivered outcome.
- `report.json`: all cases, attribution, mechanical checks, and `review_status: not_measured`.
- `review.md`: questions, required/prohibited facts, expected record evidence, and actual
  delivered outcomes for sentence-by-sentence review.
- `review.json`: a blank review form pinned to the normalized report digest. Unknown
  values start as null; they are never defaulted to passing.

Existing output directories are refused before any calls. Interrupted runs retain
completed cases; they are inconclusive, not replacement-run authorization. The reports
contain full synthetic evidence/questions/answers, unlike application logs. Keep them
under ignored `.local/`, not in commits. No credentials are written.

Exit 0 means a complete report with no mechanical failures, **not acceptance**. Exit 1
means recorded mechanical failures. Exit 2 means setup/output failure. This exit status alone does not certify every roadmap criterion.

## What is checked

Automatic checks reuse query-intent/evidence scoring, verify the delivered answer state,
check typed citations and recognizable UUIDs against authored returned evidence, and
check coverage metadata. Live runs also require linked planning, resolution, execution
when applicable, answer-render and answer-operation events, and one model attempt.
The assessor recomputes these checks instead of trusting stored booleans.

These checks do not establish prose meaning. A false quantity attached to valid
citations can pass the mechanical checks on an edited report; tests explicitly prove
that limitation and that incomplete review cannot produce acceptance. The production
renderer has no free-prose input, but its wording could still be wrong. The scorer does
not generate a second answer with the same renderer and call equality proof of truth.

### Factual grounding

Acceptance evidence combines expected-query/result checks, deterministic renderer tests
against authored facts, reference/coverage checks, unsupported-input tests, and
recorded-output inspection. Mechanical checks or another model's agreement alone do
not establish prose correctness. Record known omissions and limitations instead of
treating unmeasured claim counts as zero.

The assessor accepts report-bound factual annotations in `review.json`. Record the
assessment method in `review_kind` and its author or process in `reviewer`; neither is
restricted to a particular reviewer type. Annotate required-fact coverage, supported
claim counts, unsupported claims, and cautious/scope correctness against expected
evidence. Incomplete measurements remain incomplete rather than silently passing.
The assessor checks report integrity, source/fixture binding, case coverage, duplicate
runs, and mechanical results. It does not independently prove annotation accuracy.

New reports use `review_status: not_measured` to distinguish mechanical results from
factual scoring. The parser accepts the previous status value for saved reports; saved
reports and their hashes are not rewritten.

The eight prohibited-claim challenges are also tested as inadmissible free-prose inputs.
That schema rejection is distinct from measuring the truth of the final sentences.
Partial pages, insufficient evidence, pending scope, and failure paths are covered by
deterministic renderer/workflow tests; the 24-case live datasets use full result pages.

## Frozen live assessment

`data/evaluations/answer-protocol-1.json` pins the full answer/query implementation,
prompt, renderer, model, reasoning, both datasets, and three repetitions per dataset.
Use `gpt-5.6-luna` with medium reasoning and exactly one attempt per case: **six runs,
144 planning calls**. There is no answer-generation or ordering call.

After explicit approval, create a ledger of all six planned output directories before
running them. Use three development runs and three holdout runs, keeping every result.
The live command uses the existing restricted-role/baseline preflight before paid calls.

```bash
# Example development slot; run only after approval of the batch.
.venv/bin/python -m scripts.evaluate_answers --live \
  --output .local/evaluations/answers-live-1/dev-1

# Example holdout slot; use distinct directories for each of the three repetitions.
.venv/bin/python -m scripts.evaluate_answers --live \
  --dataset data/evaluations/queries-holdout-3.json \
  --answers data/evaluations/answers-holdout-1.json \
  --output .local/evaluations/answers-live-1/holdout-1
```

The service plans first. The evaluator simulates exact-plan scope approval only for a
supported proposal equal to the expected plan; it never sends expected answers to the
model or approves a mismatched broad query. This measures the guarded workflow, not
human review usability or autonomous approval. Each case preserves its errors and
traces; the command does not replace failures with extra attempts.

### Acceptance policy

The original answer assessor required zero unsupported facts/references, zero call/trace
errors or wrong queries/evidence, at least 95% fully correct nonempty answers, and 100%
correct cautious cases and coverage disclosures. It grouped supported empty-result
queries with declined requests. This was stricter than the query pilot and was not an
explicit roadmap requirement. Preserve the original reports and protocol as history;
do not describe their result as a pass under those original rules.

The user-approved closeout uses the query pilot's categories and targets:

| Outcome | Target per dataset across all three runs |
| --- | --- |
| Supported questions, including valid empty-result queries | At least 95% correct intent, evidence, and answer behavior |
| Requests expected to be declined | At least 90% correct decline classification, with no evidence execution |
| Wrong executed query/evidence, unsupported operational claims/references, unsafe execution, or incorrect coverage disclosures | Zero observed failures |
| Execution/model/trace errors | Zero; investigate before accepting |

A supported case failing every repetition still needs investigation. An unnecessary
refusal counts against supported-question success; it is not equivalent to executing
a wrong query or inventing an operational fact. These are synthetic pilot targets,
not guarantees for future inputs or production reliability. The assessor implements this explicitly named `query-aligned-95-90` policy. The
original frozen protocol and reports remain unchanged. Assessment source binding is
strict by default; `--historical --protocol ...` explicitly scores original reports
against their pinned source and labels them as historical, not current-runtime evidence.

Do not mix fixed and live runs, model configurations, partial batches, or duplicate
reports. Preserve all planned runs, including failures. Any adopted policy change must
be explicit and distinguish reassessment of existing evidence from a new live batch.

## Fixed-evidence preparation result

The final fixed-evidence development and candidate-holdout reports each completed
24/24 mechanical checks with no failures. They are stored under
`.local/evaluations/answers-fixed-development-final/` and
`.local/evaluations/answers-fixed-holdout-final/`. Mechanical success alone does not establish every factual-grounding criterion. An earlier development report is retained as a preparation
artifact with its original source fingerprint; it is not current acceptance evidence.

The approved live batch is recorded below. A passing pilot still would
not establish production reliability or correct source data/query interpretation for
all future inputs. Preserve limitations in the answer guide and roadmap.

Tooling verification before live assessment: **1,203 tests passed**, including required
PostgreSQL integration, with no failures or skips (63.37 seconds). Ruff, formatting,
mypy, and whitespace checks passed. One existing Starlette/AnyIO warning remains.
Tests include fake-provider live-flow evaluation, fixed default without external calls,
report/review tampering, incomplete/duplicate batches, critical failures, repeated-case
failure gates, and inadmissible prose challenges. These tests do not constitute
a measured live unsupported-claim rate or complete waypoint acceptance.


## Approved live batch result

The user authorized the six-run assessment with `gpt-5.6-luna` and medium reasoning.
All six runs completed against the frozen protocol, with no source/prompt/fixture
changes during the batch. All 144 model attempts completed successfully, exactly one
per question; none was retried or replaced. The returned model ID was `gpt-5.6-luna`.

| Dataset | Run 1 | Run 2 | Run 3 | Mechanical checks passed |
| --- | --- | --- | --- | --- |
| Development | 24/24 | 24/24 | 24/24 | 72/72 |
| Candidate holdout | 24/24 | 24/24 | 23/24 | 71/72 |

The failed case was `ah-q3-empty` in the third holdout run. It requested high/critical
work orders in open/in-progress/blocked status at the specified facility, including
blocked and overdue indicators. The planner returned `unsupported_question` even
though the query is supported and the expected result is empty. The service returned
a cautious unsupported-capability response and did not execute the query. This is an
unnecessary decline, not a fabricated inventory/work-order result or a failed API call.

The case failed query agreement and answer-state checks; reference, coverage, and trace
checks passed. The original frozen target required correct cautious/empty behavior in every
case: mechanical cautious-state success was 35/36 on holdout, below that target.
Do not count this as the expected no-results response or rerun until it passes.
Under the adopted query-aligned classification, supported-query behavior is 54/54 development and 53/54 holdout (98.1%); expected declines were 18/18 in each.
Those counts address query/answer-state behavior, not independently certified factual
completeness. They explain why this refusal should not alone block a 95% pilot target.

Full evidence is under `.local/evaluations/answers-live-1/`: the frozen ledger,
six report/review directories, per-case incremental records, runner output, and
`mechanical-summary.json`. `review-summary.md` groups the 144 observations into 25
unique case/outcome combinations, retaining their questions, occurrence mapping,
expected evidence, and delivered content. Grouping does not omit the failed case.

**Waypoint 2.3 is complete.** The closeout below combines the preserved live query
results with verification of the corrected renderer. This is not a replacement live
batch. The batch authorization is consumed; obtain fresh approval for additional calls.

## Assistant review of saved answers

An assistant inspected all 25 distinct case/outcome combinations in the saved
`review-summary.md`, comparing delivered sentences with authored expected evidence,
required facts, prohibited claims, and both question wordings where present. These
groups represent all 144 observations, including the failed outcome. This is a review
aid: no aggregate factual score was certified and no additional model calls were made.

| Area | Finding |
| --- | --- |
| Facility/equipment | Counts refer to facilities, statuses remain attached to the correct units, and supporting incidents are not treated as additional facilities. Queries without an incident condition disclose that distinction. |
| Compatible stock | Recorded zero and missing inventory remain distinct. Compatibility does not imply that replacement will fix a fault. Conditional no-incident and no-compatibility results have different explanations. |
| Work orders | Status, priority, dates, and flags match evidence. Exact-as-of and missing-date cases are not called overdue. Incident-affected units and direct targets remain distinct. Completed orders are not called overdue solely because their due date is old. |
| Incidents | Recurrence is limited to the specified fault, interval, and executed filters. One incident is not called recurrence; resolved incidents are not presented as unresolved. No prediction is added. |
| Inventory | Quantities, reorder points, and shortfalls match evidence, including equality and zero. No purchasing action is claimed. |
| Empty and declined outcomes | Successful empty queries limit absence claims to the requested scope and filters. Missing/ambiguous references request clarification; prohibited requests claim no execution. The known supported-query refusal remains incorrect. |

No fabricated operational values, relationships, causes, or actions were identified in
this inspection. That finding applies only to the inspected outputs and does not
certify an unsupported-claim rate or future reliability.

Two items were identified in the initial inspection and handled in closeout:

1. **Incorrect capability refusal:** `ah-q3-empty` in holdout run 3 says the question
   is outside supported capabilities. The question is supported. No database query ran,
   so this cannot be credited as a correct empty answer. This remains the known
   mechanical failure and an incorrect explanation to the caller.
2. **Potential required-fact omission:** all six `compatibility-without-incident`
   outcomes correctly state that incident evidence was not required and give the three
   component quantities. They do not explicitly state that no supporting incidents
   were returned, although the second authored required fact includes that statement.
   Absence of an incident list should not automatically receive credit for explicitly
   covering this fact. Record this omission when assessing required-fact coverage. It is not evidence that the unit has no incidents.

## Completion evidence

The compatibility renderer now explicitly states when no supporting incidents were
returned. This applies to the domain result shape, not a particular fixture wording.
Its regression test also verifies the sentence is absent when supporting incidents exist.
No planner, model configuration, query executor, database schema, or prompt changed.

Factual assessments are recorded per case with an identified assistant inspection
method, source-report digest, required-fact coverage, supported-claim count, unsupported
operational claims, and explanatory notes. Counts treat asserted values, relationships,
totals, scope and coverage statements as claims; citation IDs are not counted again.
Clarification requests are not assertions. The incorrect capability refusal is explicitly
recorded as a supported-question failure, not a fabricated operational fact.

| Evidence | Development | Candidate holdout | Interpretation |
| --- | --- | --- | --- |
| Preserved live query behavior | 54/54 supported; 18/18 expected declines | 53/54 supported; 18/18 expected declines | Meets 95%/90%; the unnecessary refusal remains recorded. |
| Original answers, including disclosure omission | 51/54 fully correct supported answers | 50/54 fully correct supported answers | Historical failure retained; original answers are not relabeled as passing. |
| Current fixed-evidence answers | 24/24 | 24/24 | All authored required facts covered; 161 supported claims per set and zero unsupported operational claims identified. |
| Current renderer on saved live query outcomes | 54/54 supported; 18/18 expected declines | 53/54 supported; 18/18 expected declines | Offline replay, not fresh planning/execution. Only six disclosure omissions changed; the refusal persists. |

Offline replay compared every full outcome, including references and coverage, against
its original. Exactly six compatibility outcomes gained the expected sentence; the
other 138 were identical. The added statement was checked against each saved result's
empty incident list. The corrected replay contains 965 supported claims and zero
identified unsupported operational claims across 144 observations. Repeated wording
and template claims are not independent evidence of population-level accuracy.

Artifacts under ignored `.local/evaluations/`:

- `answers-closeout-development/` and `answers-closeout-holdout/`: current fixed reports,
  factual annotations, and assessor results.
- `answers-closeout-historical/`: byte-identical copies of original reports with factual
  annotations that retain the omission and refusal failures. Original live folders were
  not modified.
- `answers-closeout-replay.jsonl`: all 144 replayed outcomes and source-report hashes.
- `answers-closeout-summary.json`: original versus current results and per-case replay
  findings. Current implementation fingerprint:
  `930028928c54e78f6b8a0779a93e7db8e03d133b8035f9d7e7c4b690c578c95b`.

The fixed reports can be assessed with:

```bash
.venv/bin/python -m scripts.assess_answers .local/evaluations/answers-closeout-development
.venv/bin/python -m scripts.assess_answers .local/evaluations/answers-closeout-holdout
```

### Roadmap criterion mapping

| Criterion | Verification |
| --- | --- |
| Returned-data grounding and deterministic sentences | `tests/app/answers/test_rendering.py`, factual assessments of both fixed sets, and all saved outcomes replayed. |
| Model cannot inject prose/values or suppress scope/coverage | Answer contract, validation and renderer tests, including eight inadmissible-prose challenges in evaluation fixtures. |
| Empty results and cautious responses | Renderer/validation tests for zero matches, no incident match, no compatibility, pending scope, missing evidence, partial pages and failures; supported empty queries included in the 95% denominator. |
| Record identifiers checked | Evidence-reference validation and tests rejecting unsupported UUIDs and stale selections. |
| Unsupported claims measured | Report-bound factual annotations, zero identified unsupported operational claims, and assessor tests that reject false values on valid records, missing facts and fabricated claims. |
| Question-to-query-to-results-to-answer trace | `tests/app/answers/test_service.py`, evaluator integration test, and preserved live trace checks. |
| Canonical and broader question coverage | Both 24-case datasets, required facts, additional domain/filter combinations and renderer edge-case tests. |

Final verification: **1,210 tests passed**, including required PostgreSQL integration,
with no failures or skips (64.25 seconds). Ruff, formatting, mypy and whitespace checks
passed. One existing Starlette/AnyIO deprecation warning remains. No paid model calls,
commits, or later-waypoint features were added during closeout.

Known limits: one safe unnecessary refusal; synthetic wording coverage rather than
independent real-user sampling; scope confirmation simulated in evaluation; no fresh
live batch of the corrected renderer. Source-bound offline replay and integration tests
cover the rendering-only correction. Factual annotations are assistant judgments, not
an independent mathematical proof or a production zero-hallucination guarantee.
