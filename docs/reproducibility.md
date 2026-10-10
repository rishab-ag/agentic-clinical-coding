# Milestone 8 run and review instructions

Docker Compose's default is a finite no-key example job, not a web server. The
image copies only app/data/examples and requirements, installs pinned dependencies,
and runs as UID 10001. It does not copy `.env`, Git history, host input records,
virtual environments or output. Compose mounts `./input` read-only at `/in` and
passes no model environment variables. Both TTY and interactive stdin are disabled.
Container output is JSONL; diagnostic logs go to stderr. Compose `up` itself adds
log prefixes; use `run` when piping results. Build requires network access, runtime
requires no downloads. The Python base tag is not digest-pinned; full bit-for-bit
image reproducibility is not claimed.

```sh
mkdir -p out
docker compose build
docker compose up --abort-on-container-exit --exit-code-from app
docker compose run --rm app --input /in/example.jsonl > out/docker-output.jsonl
```

The committed `input/example.jsonl` contains two non-clinical ingestion records,
including an empty record; it has no evaluation labels. Put arbitrary TXT, JSON or
JSONL files under `input/` (ignored except the example), and run:

```sh
docker compose run --rm app --input /in/custom.jsonl > out/custom-output.jsonl
```

You can override the input bind mount for an existing host directory:

```sh
docker compose run --rm -v "$PWD/examples:/in:ro" app --input /in/messy_note.txt
```

To use the optional model in a container, explicitly pass exported variables:

```sh
docker compose run --rm -e OPENAI_API_KEY -e OPENAI_MODEL -e OPENAI_CONTEXT_LIMIT app --input /in/example.jsonl
```

This is opt-in and requires the original-note/corpus context to fit. It is not
part of the no-key validation gate. Never put credentials into build arguments,
image files or Git. Local `python -m app.main --input PATH` supports arbitrary
paths and emits identical JSONL to stdout and `--output`. Run in an activated venv
with `pip install -r requirements.txt`; use `requirements-lock.txt` to match
container dependency versions. The lock records the tested Python 3.9 environment,
including compatibility packages that are harmless on Python 3.12.

JSONL validation (not a clinical evaluation):

```sh
python - <<'PY'
from pathlib import Path
from app.models import CodingResult
rows = Path('out/docker-output.jsonl').read_text().splitlines()
assert len(rows) == 2
for row in rows:
    CodingResult.model_validate_json(row)
print('2 schema-valid records')
PY
```

Before submission, the human reviewer should review and commit actual milestone
changes, retain real history, complete outstanding source and fixture approval,
and record actual effort. No reliable total effort ledger is available, so a
four-hour compliance claim is not made. No evaluator contact, invitation, push,
commit or email is performed by this workflow.

Outstanding gates: Docker build/up/arbitrary mount execution; independent approval
of the ten clinical fixtures; independent review of all 50 guideline drafts;
source/version/URI/reuse approval for external proposals; approved clinical
accuracy evaluation and live-model evaluation. An unresolved no-key demonstration
is intentional, not a forced clinical coding pass. Software checks do not close
these gates. See the Milestone 3 deferral in `milestone_status.md`.

## Executed validation (2026-10-10)

| Command/check | Actual result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | 181 passed, 1 skipped (opt-in live test). Initial run found 12 duplicate-module collection errors from `out/clean-run/tests`; adding `pytest.ini` with `testpaths = tests` fixed discovery. |
| `out/clean-run/.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r out/clean-run/requirements-lock.txt` | Initial sandbox request failed DNS resolution; authorized network retry downloaded and installed all pins successfully. |
| `.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt` (fresh export) | Passed; installed locked dependencies satisfy the documented requirements. |
| `.venv/bin/python -m pip check` (fresh export) | No broken requirements. |
| `env -u OPENAI_API_KEY .venv/bin/python -m pytest -q` (fresh export) | 181 passed, 1 skipped. |
| `.venv/bin/python -m app.main --no-model --input input/example.jsonl --output out/milestone8_batch.jsonl` | Two unresolved records, including the empty record. JSONL stdout matches output bytes. |
| `.venv/bin/python -m app.main --no-model --input examples/messy_note.txt --output out/milestone8_messy.jsonl` | One schema-valid unresolved record. Original note retained. |
| `env -u OPENAI_API_KEY .venv/bin/python -m app.main --input examples/messy_note.txt --output out/messy.jsonl` (fresh export) | Passed without `.env`, a key, or `.git`; one schema-valid record. |
| `env -u OPENAI_API_KEY .venv/bin/python -m app.main --input input/example.jsonl --output out/batch.jsonl` (fresh export) | Passed; two schema-valid records; stdout/output parity. |
| `env -u OPENAI_API_KEY .venv/bin/python -m app.main --input 'out/arbitrary input.txt' --output out/arbitrary.jsonl` (fresh export) | Passed; arbitrary path containing spaces; original note and stdout/output parity checked. |
| `docker --version`, `docker compose version` | Command not found. |
| `docker compose build` | Exit 127: Docker unavailable; build not performed. |
| `docker compose up --abort-on-container-exit --exit-code-from app` | Exit 127: Docker unavailable; startup not performed. |
| `docker compose run --rm app --input /in/example.jsonl` | Exit 127: Docker unavailable; mount/pipe execution not performed. |
| `git diff --check`, `git diff --cached --check` | Passed. |
| `git status --short`, `git log --oneline -8` | Inspected existing real history; no commit created. |
| Protected-data byte comparison against `HEAD` | Supplied catalogue/guidelines, derived drafts, external proposals, clinical fixtures and review packet unchanged. |

The fresh export was assembled from tracked and intended new working-tree files
under ignored `out/clean-run`, with a newly created venv. It is a working-tree
reproducibility check, not a claim that uncommitted packaging already exists in a
clean Git clone. All generated artifacts and host custom input are ignored.

## Subsequent Docker verification (2026-10-10)

Docker is now available. `docker compose config --quiet`, `docker compose build`,
`docker compose up --abort-on-container-exit --exit-code-from app`, and
`docker compose run --rm app --input /in/example.jsonl` passed. The build initially
failed accessing sandboxed buildx state, then passed with authorized access.
The example startup exited zero; stdout batch parsing found exactly two valid
CodingResult objects. `docker compose run --rm -v "$PWD/out:/in:ro" app
--input /in/fixture_notes.jsonl --no-model` also passed: ten schema-valid unresolved
results, one per fixture note, with immutable note text preserved. These checks
supersede the historical Docker-unavailable results above. They are structural
checks, not clinical evaluation. No live model was called.

The fixture file was restored to one-object-per-line JSONL with unchanged values.
Approval validation still fails for E02–E05, E07 and E10 due to prose conditions.
Reviewer notes still contain draft approval-required wording; no review conclusions
were fabricated. All 50 guideline drafts and both external proposals remain
unverified. The pending-fixture model unit test was isolated onto a non-clinical
dummy file so it no longer depends on the changing clinical review file. Full
pytest then passed: 181 passed, 1 skipped. Initial run: 180 passed, 1 failed,
1 skipped due to the fixture-file dependency. Supplied/derived/expanded data
byte comparisons against HEAD passed. Git diff checks passed.
