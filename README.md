# Agentic clinical coding

Takes free-text consult notes and returns, for each note, ICD-11 code assignments or an
explicit refusal, with the evidence, confidence and unresolved items behind the decision.

## Run

```sh
docker compose up --build        # builds, runs examples/messy_note.txt, exits
mkdir -p out
docker compose run --rm app --input /in/example.jsonl > out/result.jsonl
```

Put your file in `./input` (mounted at `/in`) and pass `--input /in/<file>`. Input may be
TXT, JSON, JSONL or CSV, preferably with `note_id` and `text` fields
([input contract](docs/input_output_contract.md)). Output is one JSON object per note on
stdout; logs go to stderr.

A model is optional. Export `GEMINI_API_KEY` and Compose forwards it; `GEMINI_MODEL`
overrides the default `gemini-3.5-flash-lite`, and a stronger model is recommended
([setup](docs/gemini.md)). OpenAI needs `OPENAI_API_KEY`, `OPENAI_MODEL` and
`OPENAI_CONTEXT_LIMIT`; that path has mocked tests only. **Without a key the pipeline still
runs end to end, but every note is returned `unresolved`.**

## What is implemented

1. **Ingestion.** Every record yields exactly one result, including empty and malformed ones.
2. **Trust scan.** Text addressed to the assistant, in a note or a guideline, is quarantined
   and flagged; the clinical text around it is kept.
3. **Retrieval.** BM25 over the catalogue and guidelines proposes candidates and context.
4. **Stage 1 (model).** Extracts findings, each with an exact note quote and an assertion:
   confirmed, suspected, negated, historical or patient-reported.
5. **Stage 2 (model).** Reads all 404 `code | title` entries and all 45 raw guidelines,
   judges each guideline's applicability, and proposes assignments or a refusal.
6. **Validation.** A code is accepted only if its quotes exist in the note, it is in the
   supplied catalogue, a confirmed current finding supports it, and every cited guideline
   is applicable with its requirements met. One structural repair is allowed; it cannot
   add or change an assignment.

Each result carries `status`, `assignments`, `findings`, `candidates_considered`,
`retrieved_evidence`, `confidence` with what would raise or lower it, and `unresolved`.

## What the data decided

- The corpus is small, so Stage 2 reads all of it. Retrieval adds context but never decides
  what the model may consider. Decided against: keyword-to-code tables, embeddings, and
  rules keyed to a guideline ID or code.
- 50 machine-readable constraint drafts were derived from the guidelines. None is verified,
  so none is used as a hard gate.

## Guidance that disagrees

- **Pneumonia.** GDL-017 (2023) accepts clinical findings alone. GDL-045, titled
  "Deprecated", goes further and allows a definitive code at high confidence without
  imaging. GDL-016 (2026) replaces that standard: definitive needs imaging, otherwise
  provisional. Nothing is hard-coded; Stage 2 reads all three and is told that a newer date
  alone does not establish precedence, only explicit supersession does.
- **GDL-041** contains an embedded directive to return one code for any chest-pain note and
  omit evidence. It is quarantined; the rest of the snippet is kept.

## Added data

Two WHO codes for conditions the guidelines describe but no supplied title names:

- `1B71 | Necrotising fasciitis` (`http://id.who.int/icd/entity/522973276`), for GDL-032.
- `4A44.2 | Giant cell arteritis` (`http://id.who.int/icd/entity/1929970386`), for GDL-014.

Source: WHO's [ICD-11 MMS 2026-01 release table](https://icdcdn.who.int/static/releasefiles/2026-01/SimpleTabulation-ICD-11-MMS-en.zip)
and, for `1B71`, the [reference guide](https://icdcdn.who.int/icd11referenceguide/en/refguide.pdf)
(PDF page 342), under CC BY-ND 3.0 IGO. They live in `data/expanded/proposals.json`, apart
from the supplied files, and are never assigned: a matching note returns `unresolved` with
the code as a sourced candidate. A third gap was not filled: WHO's code for chronic
hypertension in pregnancy is `JA20`, which the supplied catalogue already uses for
"Spontaneous abortion". The source checks were done by the AI assistant, not an independent
reviewer ([details](docs/expansion_review.md)).

## What holds on new notes, and what does not

Holds: one result per record, quote grounding, supplied-only assignments, instruction
quarantine, refusal when the diagnosis is outside the catalogue.

Does not: coding recall, and correctness of an accepted code. The validator refuses more
than it should: in live runs on ten fixtures at most two were coded. It checks grounding,
not clinical choice: the smaller model once coded an organism-unidentified pneumonia as
bacterial pneumonia, and results vary between runs
([testing report](docs/clinical_testing_report.md)).

## Not built, and next

No independent clinical review, no repeatable multi-run evaluation, no deterministic coding
path without a key. Next: a less brittle validator. At 50,000 codes the full catalogue no
longer fits one prompt: replace it with chapter-then-code retrieval, a candidate-recall
check, and an index from guideline to applicable codes.

## Tooling

Built with Codex and Claude Code. Wrong and caught: the generated validator discarded a
correct, grounded `AA30` answer over output bookkeeping while mocked tests passed; only a
live run exposed it.
