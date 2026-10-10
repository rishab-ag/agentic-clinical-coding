# Gemini provider

Google AI Studio keys can be used with the new `GeminiModel` adapter. It uses
stdlib HTTPS, a fixed Google generateContent endpoint and an `x-goog-api-key`
header; keys are never placed in URLs or logged. Local Pydantic/source-evidence
validation remains authoritative. No clinical labels or approval flags changed.

In your ignored `.env`, configure these variables:

```dotenv
MODEL_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
GEMINI_MODEL=<supported-model-ID-from-AI-Studio>
GEMINI_CONTEXT_LIMIT=<verified-input-context-limit-for-that-model>
GEMINI_MAX_OUTPUT_TOKENS=4096
GEMINI_TIMEOUT_SECONDS=30
GEMINI_RETRIES=1
CLINICAL_CONCURRENCY=1
```

`.env` is not automatically read. Export these variables in your terminal, or
load your own trusted shell-compatible `.env` without echoing credentials:

```sh
set -a
source .env
set +a
mkdir -p out
python -m app.live_eval --live --split development > out/gemini-development.json
```

Keep `.env` untracked; `.env.example` contains only placeholders. An OpenAI key
must not be used as a Gemini key. Explicit provider selection avoids ambiguity
when both keys are present. With no selected-provider key, processing remains
offline. `--no-model` always forces offline processing.

For Docker, `compose.yaml` forwards these variables when they are exported or
present in an untracked `./.env`; unset variables leave the container offline:

```sh
docker compose build
docker compose run --rm app --input /in/example.jsonl
```

Wire format follows [Google's structured-output REST documentation](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en):
trusted system instructions are separate from user source content, and the JSON
schema is sent under `generationConfig.responseJsonSchema` with
`responseMimeType=application/json`, as documented in the
[generateContent API reference](https://ai.google.dev/api/generate-content?hl=en). Google supports a
subset of JSON Schema; unsupported model/schema combinations are refused rather
than silently using unconstrained text. Only a single candidate with `STOP` finish
reason, output text and actual `usageMetadata.promptTokenCount` is accepted.
Thought parts are excluded. Blocked/truncated/refused responses cannot assign.

Prompt preflight uses the actual serialized Gemini payload's UTF-8 bytes plus
1024 framing reserve, explicitly an upper-bound estimate, not tokenizer usage.
Returned input-token usage is recorded with Gemini provenance. HTTP retries are
bounded by existing configuration; structural repair disables transport retries
and remains at most one request per note. Errors are sanitized. Model IDs are
restricted to simple identifiers to keep credentials on the fixed endpoint.

A Gemini key does not guarantee free access: check your model's
[free-tier pricing](https://ai.google.dev/gemini-api/docs/pricing) and project quota.
No billing configuration or model defaults are changed by this adapter. Google
lists free-tier content as used to improve products; this assignment uses synthetic
notes only. Do not treat mocked transport tests as API compatibility, clinical
quality, a free-tier guarantee or live evaluation.

No live Gemini request was made during implementation. Choose the model in AI
Studio and verify its context/schema support before running development evaluation.
Keep held-out evaluation for the final frozen configuration.

## Diagnosing a nonzero evaluation exit

A failed rubric returns exit 1; redirection hides the report from the terminal.
The runner now emits a short stderr summary and includes `model_diagnostics`
with per-note status, provenance/token usage and sanitized refusal reasons.
Run one development note before spending quota on the entire batch:

```sh
python -m app.live_eval --live --split development --note-id E01 > out/gemini-E01.json
python -m json.tool out/gemini-E01.json
```

On 2026-10-10, a single-note diagnostic using the saved local configuration
received HTTP 400 with no model output/token usage. The exact cause was not
established; raw HTTP responses and keys were not logged. This is not a fixture
approval problem and not evidence of clinical model performance. The earlier
seven-case report lacked model diagnostics, so its underlying model failures
cannot be reconstructed from the rubric scores alone. No held-out live run or
clinical-label change was made during diagnosis. Your shell's exported environment
and the agent's process environment are separate; `.env` remains explicitly loaded.

## HTTP 400 request-format fix

A minimal non-clinical probe established that `responseFormat.text.mimeType`
rejects `application/json`: Google reports that this field is an enum. The
adapter now uses `responseMimeType` plus `responseJsonSchema`, retaining the
full local schema validation and evidence gates. The original mocked tests
missed this API compatibility error; they now assert the corrected wire fields.
The compatible minimal request encountered HTTP 503 high demand, which is
a separate service availability issue, not a rubric or approval failure.
No raw error responses or credentials are logged by the production adapter.

## Slow responses and Python 3.9 timeout accounting

Set `GEMINI_TIMEOUT_SECONDS=120` for slower responses, then reload exported
variables. The shared configuration permits network timeouts up to 120 seconds;
30 seconds remains the code default. On Python 3.9, `socket.timeout` can be distinct
from builtin `TimeoutError`; both are now caught and converted into sanitized
provider failures with elapsed time and retry counts. Timeout retries remain
bounded by `GEMINI_RETRIES`, and repair still makes one request with no retries.
A longer timeout cannot resolve persistent Google overload or guarantee output.

```sh
set -a
source .env
set +a
python -m app.live_eval --live --split development --note-id E01 > out/gemini-E01.json
python -m json.tool out/gemini-E01.json
```

The ignored local `.env` timeout was updated to 120 without displaying or changing
its key. No live request was made during this timeout fix.

## Stage 1 schema diagnostics and numeric representations

A live E01 response passed HTTP parsing but failed the local fact validator at
`facts.1`. The live report now names schema locations and error types, without
logging raw outputs or arbitrary extra-property names. The fact validator rejects
known numeric facts represented as strings or nonfinite values. To accommodate
JSON representation differences, plain finite decimal/exponent strings in age,
gestation or duration facts are normalized to numbers before validation. Units,
certainty, assertions, note text and evidence are unchanged. Words, unknowns,
unit-bearing strings and nonfinite representations are not converted into numbers.
Original-note grounding is still required after normalization. No extraction
repair or clinical upgrade was introduced.

Full pytest after this change: 208 passed, 1 skipped. The no-key messy-note smoke
and diff check passed. A one-note live verification is recorded separately; schema
success is not a claim of clinical correctness or a guaranteed coded output.

The initial numeric representation normalization alone did **not** resolve the
live response: `facts.1` still failed, with value type `str`. The extraction prompt
and schema description now explicitly require numeric values without prose/units,
or null with unknown certainty when no number can be established. A malformed
or ambiguous fact is not guessed into a numeric value or clinical certainty.
Schema diagnostics now report only field/type information, redacting arbitrary
extra-field names. Current full tests: 208 passed, 1 skipped; diff checks passed.

Live verification after the prompt clarification passed Stage 1 (471 actual input
tokens) and reached Stage 2 (21,099 actual input tokens). Stage 2 returned an
incomplete/refused response; its exact finish reason was not recorded by the old
message. The adapter now reports sanitized finish reasons, including MAX_TOKENS
and safety blocks. The ignored local `.env` output budget was increased from
4096 to 16384 to accommodate full-corpus output and model thinking; this is not
a guarantee of success or a claim that truncation was the established cause.
Reload `.env` before retrying. No assignment was accepted in that verification.

## HTTP 404 on a listed model, and free-tier quota (2026-10-10)

`gemini-2.5-flash` appears in the `models` listing for this key with
`generateContent` support, but a minimal non-clinical request returns HTTP 404
with the API message that the model "is no longer available to new users". The
listing is therefore not proof that a model accepts requests. The `2.5-flash-lite`
and `2.5-pro` IDs returned the same 404. Current IDs that accepted the adapter's
exact request shape (`responseMimeType` plus `responseJsonSchema`) on that date:
`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3-flash-preview`,
`gemini-3.5-flash-lite` and `gemini-3.1-flash-lite`.

The free tier reported a limit of 20 `generateContent` requests per day per
model bucket; `gemini-3.5-flash` was counted against the `gemini-3.6-flash`
bucket. A note costs two requests, or three with a repair, so one bucket covers
fewer than ten notes a day. HTTP 429 and 503 are refused per note as unresolved;
they are availability failures, not model judgments. A report in which every
note shows `Gemini HTTP request failed (status 429)` is the offline baseline, not
a model evaluation.
