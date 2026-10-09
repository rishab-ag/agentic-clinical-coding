# Agentic clinical coding

Milestones 1–7 infrastructure: Python CLI, Pydantic contracts, immutable supplied corpus loaders,
guideline review, ingestion, BM25 and an optional two-stage OpenAI adapter.
Without credentials the pipeline returns unresolved results. With a configured
model/context limit it validates model proposals against original-note evidence.

Use Python 3.9+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.main --help
python -m app.main --check-data
python -m app.main --self-check
mkdir -p out
python -m app.main --input examples/messy_note.txt --output out/messy_note.jsonl
python -m app.guidelines
python -m pytest -q
```

The self-check needs no API key and emits one synthetic unresolved JSONL result.
The self-check does not process clinical notes. Implemented file formats and accounting rules
are in [docs/input_output_contract.md](docs/input_output_contract.md).
The supplied 404 catalogue records and 45 raw guidelines remain unchanged;
their contents are untrusted data. External proposals are isolated and excluded pending source/reuse review.
Guideline drafts cover every snippet and remain **uncertain** pending independent
human review. See [the review workflow](docs/guideline_review.md) for source
quotes/hashes, three-valued evaluation, proposed relationships and trust warnings.

Built with Codex. Clinical evaluation and live model testing have not occurred.
An initial trust-screening change missed `AI INSTRUCTION`; a failing non-clinical
regression test exposed it, and the generic marker rule was corrected.
The [evaluation harness](docs/evaluation.md) awaits human approval of fixtures;
the live runner currently skips without making model calls.
See [model configuration and limits](docs/model_reasoning.md) for environment
settings, prompt accounting, trust boundaries and opt-in live evaluation.
Milestone 3 clinical approval is **deferred**, not passed; labels and guideline
drafts remain unapproved. See [milestone status](docs/milestone_status.md) and
[the Milestone 4 report](docs/milestone4_report.md) for the actual vitiligo retrieval
hits and refusal rationale. At 50,000 codes, full catalogue context would require
hierarchical retrieval and indexed guideline applicability; this is a small-corpus
prototype. The [external review packet](docs/expansion_review.md) documents the necrotising-infection gap, WHO source observations and supplied-code conflicts; no external entry is independently approved.
Later milestones remain subject to human review; Codex does not commit.
