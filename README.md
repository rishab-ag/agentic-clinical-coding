# Agentic clinical coding

Milestones 1–3 scaffolding: Python CLI, Pydantic contracts, immutable supplied
corpus loaders, guideline review, and evaluation runners. No retrieval,
clinical coding, or model calls yet.

Use Python 3.9+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.main --help
python -m app.main --check-data
python -m app.main --self-check
python -m app.guidelines
python -m pytest -q
```

The self-check needs no API key and emits one synthetic unresolved JSONL result.
It does not process clinical notes. Planned file formats and accounting rules
are in [docs/input_output_contract.md](docs/input_output_contract.md).
The supplied 404 catalogue records and 45 raw guidelines remain unchanged;
their contents are untrusted data. No external additions have been made.
Guideline drafts cover every snippet and remain **uncertain** pending independent
human review. See [the review workflow](docs/guideline_review.md) for source
quotes/hashes, three-valued evaluation, proposed relationships and trust warnings.

Built with Codex. Clinical evaluation and live model testing have not occurred.
The [evaluation harness](docs/evaluation.md) awaits human approval of fixtures;
the live runner currently skips without making model calls.
Later milestones remain subject to human review; Codex does not commit.
