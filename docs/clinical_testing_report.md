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
