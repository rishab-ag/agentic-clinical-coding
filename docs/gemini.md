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

For Docker, explicitly pass exported variables (Compose does not pass them by
default):

```sh
docker compose build
docker compose run --rm -e MODEL_PROVIDER -e GEMINI_API_KEY -e GEMINI_MODEL -e GEMINI_CONTEXT_LIMIT app --input /in/example.jsonl
```

Wire format follows [Google's structured-output REST documentation](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en):
trusted system instructions are separate from user source content, and the JSON
schema is sent under `generationConfig.responseFormat.text`. Google supports a
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
