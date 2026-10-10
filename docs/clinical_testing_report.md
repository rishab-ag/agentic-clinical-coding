# No-key fixture evaluation — 2026-10-10

Fresh no-key results were generated from the committed fixture notes, split into
seven development and three held-out records. All fixtures carry user-entered
approval. Six conditional expectation sets were authored by Codex and accepted
by explicit user instruction; reviewer qualifications and independent clinical
review were not verified. This report is agreement against that accepted rubric,
not independently established diagnostic accuracy.

| Check | Actual result |
| --- | --- |
| `.venv/bin/python -m app.evaluation --fixtures tests/fixtures/clinical_eval.jsonl --validate-fixtures` | Passed: ten approved records, no schema issues. The approval-count gate is met. |
| `.venv/bin/python -m pytest -q` | 184 passed, 1 skipped. |
| `.venv/bin/python -m app.main --no-model --input out/testing_development_input.jsonl --output out/testing_development_results.jsonl` | Seven structured unresolved results. |
| `.venv/bin/python -m app.main --no-model --input out/testing_held_out_input.jsonl --output out/testing_held_out_results.jsonl` | Three structured unresolved results. |
| `.venv/bin/python -m app.evaluation --fixtures tests/fixtures/clinical_eval.jsonl --results out/testing_development_results.jsonl --split development` | Exit 1: five of seven complete rubrics matched, six of seven statuses matched. |
| `.venv/bin/python -m app.evaluation --fixtures tests/fixtures/clinical_eval.jsonl --results out/testing_held_out_results.jsonl --split held_out` | Exit 1: two of three complete rubrics and statuses matched. |
| `.venv/bin/python -m app.live_eval --live` | Explicit skip: API key absent; zero model calls. Model and context variables also absent. |

Across both splits, ten notes produced exactly ten schema-valid results: no
missing, duplicate or unexpected notes, no accounting errors and no high-confidence
rubric failures. All results abstained with no assignments. Output-file bytes
matched stdout for both runs. Expected finding coverage is null because no
`expected_findings` labels are supplied; no finding recall score is inferred.

Failures:

- E01: the rubric requires `coded` and AA30. The no-key path abstains.
- E02: the unresolved branch requires a pneumonia candidate with an explicit
  imaging discriminator. The pipeline did not satisfy that predicate.
- E09 (held out): the rubric requires `coded` and CA22. The no-key path abstains.

Refusals account for the seven matches; this is not evidence of successful code
assignment. No production decision, prompt, clinical label or held-out expectation
was changed to improve these scores. No-key abstention remains conservative while
independent applicability authorization cannot be established. The clinical rubric
validation gate is met numerically, but the evaluation pass gate is not met.

Reports and results are under ignored `out/testing_*`. For a live development
run, configure actual exported `OPENAI_API_KEY`, `OPENAI_MODEL` and
`OPENAI_CONTEXT_LIMIT`, then use the live runner. The `.env.example` is not
automatically loaded. Do not expose credentials in terminal output or Git.
Guideline drafts and external proposals remain unverified. No new Docker run
was needed; previous Docker execution checks remain recorded separately.

## Live Gemini evaluation (2026-10-10, prompt `two-stage-v3`)

Free-tier quota (20 requests per model bucket per day) prevented a single-model
batch run, so notes were run one at a time. Results below are single runs against
the same ten fixtures; they are small-sample observations, not accuracy estimates.

| Note | Split | Model | Status | Rubric | Refusal reason recorded |
| --- | --- | --- | --- | --- | --- |
| E01 | development | gemini-3.6-flash | coded (AA30, definitive) | not scored by the runner | — |
| E02 | development | gemini-3-flash-preview | unresolved | fail | guideline review incomplete |
| E03 | development | gemini-3-flash-preview | coded | pass | — |
| E04 | development | gemini-3-flash-preview | unresolved | pass | unknown guideline applicability |
| E05 | development | gemini-3-flash-preview | unresolved | pass | unresolved finding blocks high confidence |
| E06 | development | gemini-3-flash-preview | unresolved | pass | guideline review incomplete |
| E07 | development | gemini-3-flash-preview | unresolved | pass | guideline review incomplete |
| E08 | held out | gemini-3-flash-preview | unresolved | pass | unknown guideline applicability |
| E09 | held out | gemini-3-flash-preview | unresolved | fail | required evidence not met |
| E10 | held out | gemini-3-flash-preview | unresolved | pass | guideline quote not grounded |

E01 was observed coded through a diagnostic wrapper around the same pipeline, with
no repair; a later runner batch on that model returned HTTP 429 for all seven
notes and is not a model result. E02's failure is the same exact-string
discriminator predicate that fails offline. E09 requires `coded` with CA22; the
validator refused the proposal and the cause was not investigated, to avoid tuning
on a held-out note. No assignment in any run carried a forbidden code.

Three of six development replies from `gemini-3-flash-preview` omitted some of
the 45 guideline reviews. After those runs, validation was changed so that a
refusal with omitted reviews keeps the model's dispositions and records the gap
as unknown, and a proposed assignment with omitted reviews receives the single
permitted repair, which may add missing assessments but not alter existing ones.
That change is covered by dummy-record unit tests only; development notes were
not rerun after it because quota was exhausted. The held-out notes ran after it.

### Second live pass on `gemini-3.5-flash-lite` (2026-10-10)

This model's free-tier bucket had enough quota for all ten fixtures, run one note
per process with unchanged code. Single runs, same caveats as above.

| Split | Rubric matches | Coded | Refused |
| --- | --- | --- | --- |
| development (E01–E07) | 6/7 | E01 (AA30) | E02–E07 |
| held out (E08–E10) | 2/3 | none | E08–E10 |

E02 fails the same exact-string discriminator predicate. E09 again fails because
it requires `coded` with CA22; the proposal was refused for a disposition that
named a code with no matching assignment. Refusals that passed validation carried
note-specific reasons, for example that the supplied catalogue has no entry for
the suspected condition in E06.

Run-to-run variation is real on this model. E03 was refused in all three runs,
once with a validated reason and twice on accounting; `gemini-3-flash-preview`
coded it. A second E01 run was refused after a repair altered the assignment,
so E01 coded in one of two runs. A trial change that made the
disposition-without-assignment mismatch repairable rescued nothing in three
development reruns and was reverted.

The model also returned bare finding IDs as `unresolved` entries on the example
note and two held-out notes. The prompt now requires sentence-form reasons; this
was confirmed on `examples/messy_note.txt` only. Fixtures were not rerun after
that wording change. A keyed `docker compose run` on the example note completed
in model mode and emitted schema-valid JSONL.
