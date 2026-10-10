# Agentic clinical coding

Python CLI for TXT/JSON/JSONL notes: BM25 retrieval, optional two-stage OpenAI/Gemini model
reasoning, grounded evidence validation and one bounded structural repair. Every
record produces one JSONL result with findings, confidence, citations and unresolved
issues. **No-key mode currently abstains on all notes**; it preserves input rather
than claiming clinical interpretation. Runtime needs no embedding downloads.

```sh
docker compose up --build
# Pipeable JSONL; ./input is mounted read-only at /in:
mkdir -p out
docker compose run --rm app --input /in/example.jsonl > out/result.jsonl
# Put your own file in ./input, then use --input /in/custom.jsonl.
```

Compose forwards model variables only if exported or in an untracked `.env`; a
clean clone runs offline. Its default runs `examples/messy_note.txt` and exits. `compose up` displays Compose log prefixes;
use `compose run` for machine-readable output. Build requires internet for the
base image and pinned Python packages. Docker build, no-key startup and mounted batch JSONL output have been verified.

Local alternative (Python 3.9+):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.main --input examples/messy_note.txt --no-model
python -m app.main --input input/example.jsonl --output out/local-result.jsonl --no-model
python -m pytest -q
```

`requirements-lock.txt` pins the tested dependency versions used by Docker.
The optional model reads environment variables described in
[model configuration](docs/model_reasoning.md) and [Gemini setup](docs/gemini.md); copying `.env.example` alone does
not load variables. No credentials are required for offline processing.

The unchanged 404 codes and 45 guidelines are untrusted evidence, not instructions.
GDL-016 narrows GDL-017's pneumonia confirmation standard; GDL-045 preserves older,
conflicting guidance. Stage 2 reviews the complete raw corpus and refuses unknown
applicability; source quotations cannot prove its interpretation. GDL-041 contains
an assistant-directed coding override: quarantine it while retaining benign text
and warnings. All **50 derived drafts remain unverified**; no human-verified hard
gates are claimed. Embeddings, LangGraph and OCR were left out to keep the text
pipeline small and avoid additional downloads and orchestration.

**Added data.** One external code is active: `1B71 | Necrotising fasciitis`
(`http://id.who.int/icd/entity/522973276`, chapter 01). GDL-032 describes a necrotising
infection and no supplied title names it, so every nearby supplied code is a wrong answer.
Sources: [WHO's reference guide](https://icdcdn.who.int/icd11referenceguide/en/refguide.pdf)
(PDF page 342) and WHO's [ICD-11 MMS 2026-01 release table](https://icdcdn.who.int/static/releasefiles/2026-01/SimpleTabulation-ICD-11-MMS-en.zip),
used under CC BY-ND 3.0 IGO with code, title and URI kept. It lives in
`data/expanded/proposals.json`, apart from the supplied files. The source check was done
by the AI assistant at my instruction, not by an independent human or clinician. An
expanded code is never assigned: a matching note returns `unresolved` with `1B71` as a
sourced candidate. A second proposal, a
[WHO skin-referral excerpt](https://cdn.who.int/media/docs/default-source/ntds/skin-ntds/common-skin-diseases-for-managemen-or-referral-at-primary-health-care-level.pdf),
stays inactive because the document is a review draft with no reuse terms. The
[source audit](docs/expansion_review.md) also records supplied titles that conflict with
WHO's guide (CA22/CA40, 8B00); the supplied files are not rewritten.

**What survives new notes.** One result per record, quotes checked against the original
note, supplied-only assignments, quarantine of instructions inside notes and guidelines,
and refusal when the diagnosis is outside the catalogue.

**What will not.** Coding recall. The validator refuses more than it should: in single
live runs on two Gemini models at most two of ten fixtures were coded, and an
imaging-confirmed pneumonia (held-out E09) was refused both times. Output varies between
runs on the smaller model, and no-key mode abstains on every note. Fixture expectations
are AI-proposed and owner-approved, not independently reviewed, so the
[testing report](docs/clinical_testing_report.md) is not an accuracy claim.

**Not built, and next.** Independent clinical review of fixtures and guideline drafts, a
repeatable multi-run live evaluation, and a less brittle validator. At 50,000 codes,
replace full-corpus prompting with hierarchical chapter/code retrieval, candidate-recall
checks and indexed guideline applicability.

**Tooling.** Built with Codex, then Claude Code for live testing and fixes. Wrong and
caught: the generated validator threw away a correct, grounded `AA30` answer on output
bookkeeping, and mocked tests passed throughout; only a live run exposed it. Earlier, a
trust-screening change missed `AI INSTRUCTION` until a regression test exposed it. See
[validation and remaining requirements](docs/reproducibility.md).
