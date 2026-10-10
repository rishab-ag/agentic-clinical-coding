# Milestone 5: optional two-stage model reasoning

The adapter follows the [official OpenAI Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
It uses Python's standard-library HTTPS client against Responses REST rather than
adding an SDK dependency. `ClinicalModel` exposes extraction/decision calls with
messages, wire schema and response usage. Local contracts and orchestration are
provider-neutral; only OpenAI is implemented. No model is implicitly selected.

## Configuration and execution

Environment variables (not Git credentials):

- `OPENAI_API_KEY`: absent means the existing offline path.
- `OPENAI_MODEL`: explicitly chosen model with structured-output support.
- `OPENAI_CONTEXT_LIMIT`: supported context capacity of that chosen model. The
  operator must verify this; it is not inferred or invented by this prototype.
- `OPENAI_MAX_OUTPUT_TOKENS`: default 4096, less than the configured context limit.
- `OPENAI_TIMEOUT_SECONDS`: default 30; maximum 60 seconds per HTTP attempt.
- `OPENAI_RETRIES`: default 1 transient retry, configurable from 0 to 2.
- `CLINICAL_CONCURRENCY`: default 1; range 1–4. Results retain input order.

The CLI does not load `.env` automatically. Supply variables through the runtime
environment; `.env.example` contains no secrets. An incomplete configured model
falls back to conservative offline mode with a stderr diagnostic. `--no-model`
forces offline operation even with credentials present.

```sh
python -m app.main --input examples/messy_note.txt --no-model
python -m app.main --input PATH --output out/model-results.jsonl
python -m app.live_eval --live --fixtures tests/fixtures/clinical_eval.jsonl
RUN_LIVE_EVAL=1 python -m pytest -q tests/test_live_model.py
```

The last two commands still skip with no key/configuration or no independently
approved selected fixtures. Default live split is development; held-out evaluation
requires `--split held_out`. No live inference or clinical scoring was performed
for this milestone: credentials are absent, and all ten clinical fixtures remain
pending. The earlier clinical gate is deferred, not passed. No guideline draft
is promoted to verified and no clinical labels/metadata are edited.

## Prompts and evidence

Stage 1 produces finding IDs, immutable quotes/offsets, assertion, temporality,
experiencer, encounter relevance, generic facts with provenance/certainty and
separate non-evidentiary differential hypotheses. Hypotheses may expand lexical
candidate recall but cannot appear in finding IDs or assignment evidence.

Stage 2 contains all 404 supplied `code | title` lines, all 45 unchanged raw
guideline bodies, their trust segment annotations, the original note, Stage 1
output, BM25 candidates/context, verified constraints and advisory relationships.
There are zero verified constraints at present. Expanded sources are explicitly
empty, awaiting their authorized milestone. Unknown applicability and unmet/
unknown required evidence block assignments; a retrieval miss never establishes
irrelevance. Newer dates alone do not determine precedence.

The output/trust contract is a trusted system message. Every source and model-
derived value is inside an untrusted JSON block in the user message. Angle
brackets in source strings are JSON-escaped so data cannot close the wrapper.
All raw snippets remain available; quarantined text is annotated as inert data.
Source warnings survive invalid decision responses. No code/guideline-ID medical
branching or disease keyword map is introduced.

Local checks enforce code/source membership, exact note/source grounding (case
and whitespace normalization only), retained note spans, Stage 1 ID preservation,
one disposition per Stage 1 finding, all-guideline review accounting, confirmed
current patient/encounter linkage for definitive assignments, and grounded
provisional-permission quotations. Applicable independently verified numeric/test
conditions are checked mechanically. Note status is derived by application code.
Application-owned input, original records, hashes, provenance and trust flags
cannot be overwritten by the proposal. No high-confidence assignment can pass
without actual original-note quotes, even when the detector misses an instruction.

These are necessary software checks, not clinical verification. In particular,
the model's interpretation that a raw quote permits provisional coding and that
its conditions apply is not independently certified. Quote existence alone cannot
prove clinical meaning. Extraction recall, supersession/clinical applicability
correctness and safety on unseen notes need independent human-reviewed evaluation.
Milestone 6's repair/reconciliation work remains separate; this milestone attempts
zero output repairs, within the at-most-one repair policy. Invalid schemas/quotes,
refusals, incomplete responses and provider failures produce per-note unresolved
results, preserving validated Stage 1 extraction or the offline fallback.

## Context, retries and accounting

Before each request the adapter measures a conservative UTF-8 request-byte bound
with a 1024 framing reserve, includes the complete wire schema and reserves output
tokens. This is an operational upper-bound estimate, **not an exact tokenizer
measurement or verified model capacity**. It is recorded separately in
`stage_prompt_upper_bounds`. If it exceeds configured capacity, abstain without
sending/truncating. API `input_tokens` supplies actual stage counts after a call;
`prompt_token_count_method` distinguishes `api_usage` from `utf8_upper_bound`.
The aggregate counts only known API usage, while unsent-stage bounds stay visible.
Actual returned usage is checked against the configured reserve as well.

For the messy-note measurement with an empty Stage 1 placeholder (not an actual
model extraction), measured bounds were 6,579 for Stage 1 and 88,533 for Stage 2,
plus 4,096 reserved output tokens each. Actual extracted findings increase Stage 2
size. The selected model/context must accommodate the measured complete request;
no notes, guidelines or catalogue titles are silently truncated. Oversized notes
can therefore abstain conservatively.

Transient HTTP 408/409/429/5xx and transport timeouts use bounded retries/backoff.
Authentication/schema errors, malformed output and refusals do not get clinical
retry/repair attempts. Error messages omit HTTP body, key and note text. Requests
set `store: false` and `truncation: disabled`; temperature is omitted for model
compatibility. Retry counts and measured successful/failed call latency are
recorded when available. Charges/costs are not estimated or fabricated. Runtime
latency includes retries for the measured call; this is not clinical performance.

## Validation limits

Mock tests exercise actual REST payload shape, required/closed schemas, both
stages, token usage, context overflow, ordered batch isolation, fabricated
codes/IDs, absent quotes, uncertain findings, missing dispositions/permissions,
incomplete/refused/malformed responses, bounded retries and pending-fixture skips.
They use non-clinical sentinels and prove software plumbing only. No extra provider
or SDK version compatibility, live API success, model quality, billing/cost, or
clinical correctness is asserted. API/model access, network availability and
human review remain external requirements.

Milestone 6 supersedes the earlier zero-repair limitation: see [reconciliation](reconciliation.md) for the single bounded structural repair and its restrictions.

Gemini is now supported through a separate native REST adapter, selected using
`MODEL_PROVIDER=gemini` and `GEMINI_*` environment settings. See `gemini.md`.
The same original-source validators and bounded repair rules apply.
