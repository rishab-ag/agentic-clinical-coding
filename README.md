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

[External proposals](docs/expansion_review.md) cover the necrotising-infection gap:
[WHO's reference guide](https://icdcdn.who.int/icd11referenceguide/en/refguide.pdf)
and [skin referral material](https://cdn.who.int/media/docs/default-source/ntds/skin-ntds/common-skin-diseases-for-managemen-or-referral-at-primary-health-care-level.pdf).
Both proposals remain pending source/reuse review and excluded from retrieval;
no approved external additions exist. Reviewed expanded-only codes would remain
unresolved candidates, never supplied-origin assignments. The source audit also
records conflicts with supplied CA22/CA40 titles; originals are not rewritten.

Accounting, provenance and quote checks generalize across notes; lexical recall,
model clinical interpretation and the narrow explicit-field offline extraction
have no demonstrated clinical accuracy. Ten fixtures are marked approved by the reviewer, but six now contain
AI-proposed executable conditions awaiting independent review; the fixture gate remains **deferred**, not passed. Single live Gemini
runs coded two of ten fixtures and refused eight, one of them (held-out E09) wrongly; see the
[testing report](docs/clinical_testing_report.md). Next day: independent clinical/source reviews and a repeatable live evaluation.
At 50,000 codes, replace full-corpus prompting with hierarchical chapter/code
retrieval, candidate-recall checks and indexed guideline applicability.

Built with Codex. An actual trust-screening change missed `AI INSTRUCTION`; a
non-clinical regression test exposed it and the generic marker rule was corrected.
See [validation and remaining requirements](docs/reproducibility.md). The human
reviews and commits milestones; no automatic commits or evaluator messages.
