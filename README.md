# Agentic clinical coding

Milestone 1 only: Python CLI scaffold, Pydantic contracts, and immutable supplied
corpus loaders. No retrieval, clinical decisions, or model calls yet.

Use Python 3.9+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.main --help
python -m app.main --check-data
python -m app.main --self-check
python -m pytest -q
```

The self-check needs no API key and emits one synthetic unresolved JSONL result.
It does not process clinical notes. Planned file formats and accounting rules
are in [docs/input_output_contract.md](docs/input_output_contract.md).
The supplied 404 catalogue records and 45 raw guidelines remain unchanged;
their contents are untrusted data. No external additions have been made.

Built with Codex. Clinical evaluation and live model testing have not occurred.
Later milestones remain subject to human review; Codex does not commit.
