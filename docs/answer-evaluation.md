# Answer evaluation

Waypoint 2.3 now has repeatable fixed-evidence and live end-to-end answer evaluation,
plus an offline assessor for completed reviews. Acceptance remains pending: mechanical
checks are not a factual review, and no live calls are authorized by this document.

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
- `report.json`: all cases, attribution, mechanical checks, and `review_status: required`.
- `review.md`: questions, required/prohibited facts, expected record evidence, and actual
  delivered outcomes for sentence-by-sentence review.
- `review.json`: a blank review form pinned to the normalized report digest. Unknown
  values start as null; they are never defaulted to passing.

Existing output directories are refused before any calls. Interrupted runs retain
completed cases; they are inconclusive, not replacement-run authorization. The reports
contain full synthetic evidence/questions/answers, unlike application logs. Keep them
under ignored `.local/`, not in commits. No credentials are written.

Exit 0 means a complete report with no mechanical failures, **not acceptance**. Exit 1
means recorded mechanical failures. Exit 2 means setup/output failure. Every complete
report still requires semantic review.

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

A human reviewer must inspect every delivered sentence against expected evidence and
record, per case:

- one boolean for every required fact, including correct record association;
- the count of supported atomic factual claims in the answer;
- every unsupported claim, including plausible causes/actions or wrong values on real
  records (an empty list only after inspecting all claims);
- whether cautious behavior, scope, and completeness wording are correct;
- notes explaining issues or non-obvious interpretations.

The review identifies its reviewer and declares `review_kind: human`. Software verifies
completeness and report binding, not the reviewer's identity or judgment. Automated
agent review or another model's agreement is not a substitute for this declared gate.
Synthetic review records used in tests are not real acceptance evidence.

```bash
.venv/bin/python -m scripts.assess_answers .local/evaluations/answers-fixed-development
```

The assessor rejects missing/null reviews, omitted or duplicate cases, incomplete fact
coverage annotations, changed report/fixture/source hashes, and inconsistent automatic
checks. Exit 0 is a reviewed single-report pass, 1 a reviewed failure, and 2 an
incomplete/incompatible assessment. A single report cannot close the frozen live batch.

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

Complete the report-bound human reviews for all six runs, then assess together:

```bash
.venv/bin/python -m scripts.assess_answers \
  --protocol data/evaluations/answer-protocol-1.json \
  .local/evaluations/answers-live-1/dev-1 \
  .local/evaluations/answers-live-1/dev-2 \
  .local/evaluations/answers-live-1/dev-3 \
  .local/evaluations/answers-live-1/holdout-1 \
  .local/evaluations/answers-live-1/holdout-2 \
  .local/evaluations/answers-live-1/holdout-3
```

Per dataset, the unchanged targets require zero delivered unsupported facts/references,
zero call/trace errors or wrong queries/evidence, at least 95% fully correct answerable
cases, and 100% correct cautious cases and coverage disclosures. A supported case failing
all repetitions fails the batch. The answerable denominator is nonempty answer cases;
empty queries and declined requests are cautious cases. Do not mix fixed and live runs,
model configurations, partial batches, or duplicate reports. Never select only good runs
or quietly weaken targets after seeing results. A report/review ledger remains a process
requirement: software cannot detect deliberately withheld runs or a dishonest review.

## Fixed-evidence preparation result

The final fixed-evidence development and candidate-holdout reports each completed
24/24 mechanical checks with no failures. They are stored under
`.local/evaluations/answers-fixed-development-final/` and
`.local/evaluations/answers-fixed-holdout-final/`. **Semantic reviews are blank and
acceptance is not claimed.** An earlier development report is retained as a preparation
artifact with its original source fingerprint; it is not current acceptance evidence.

The approved live batch is recorded below; completed human reviews remain outstanding. A passing pilot still would
not establish production reliability or correct source data/query interpretation for
all future inputs. Preserve limitations in the answer guide and roadmap.

Tooling verification before live assessment: **1,203 tests passed**, including required
PostgreSQL integration, with no failures or skips (63.37 seconds). Ruff, formatting,
mypy, and whitespace checks passed. One existing Starlette/AnyIO warning remains.
Tests include fake-provider live-flow evaluation, fixed default without external calls,
report/review tampering, incomplete/duplicate batches, critical failures, repeated-case
failure gates, and inadmissible prose challenges. These tests do not constitute completed
human factual reviews or live acceptance results.


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
checks passed. The frozen target requires correct cautious/empty behavior in every
case: mechanical cautious-state success was 35/36 on holdout, below that target.
Do not silently count this as the expected no-results response or rerun until it passes.
Possible future remedies are a separately evaluated general planner improvement or an
explicit prospective reconsideration of the tolerance for safe unnecessary declines.
Neither is implemented or used to retroactively pass this batch.

Full evidence is under `.local/evaluations/answers-live-1/`: the frozen ledger,
six report/review directories, per-case incremental records, runner output, and
`mechanical-summary.json`. `review-summary.md` groups the 144 observations into 25
unique case/outcome combinations, retaining their questions, occurrence mapping,
expected evidence, and delivered content. Grouping does not omit the failed case.

**Waypoint 2.3 remains in progress.** Human review forms are still blank, so unsupported
semantic claim counts have not been certified and the offline assessor correctly exits
2 (incomplete). The known mechanical failure would also prevent passing the current
batch even after reviews are completed. No zero-hallucination or production-reliability
claim follows from these results. The batch authorization is consumed; obtain fresh
approval for any additional live calls. No commits were made.
