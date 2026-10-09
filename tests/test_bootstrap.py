import hashlib
import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.data import DATA_DIR, load_supplied_data
from app.models import Assignment, CodingResult, Evidence, Finding, ClinicalFact, Note


BASELINE = {
    "icd_catalog.json": "f403ae0e98782a863279d62528c7312ba8dea6ffd0e97e84fbfb6c474d7bddfc",
    "guideline_snippets.json": "e9016c80e936ce38a8963a2a22db027fe15e31baa298ddf47fc55430bf2b1792",
}


def test_supplied_integrity():
    data = load_supplied_data()
    assert len(data.catalogue) == 404
    assert len(data.guidelines) == 45
    assert all(e.catalogue_origin == "supplied" for e in data.catalogue)
    for filename, expected in BASELINE.items():
        assert hashlib.sha256((DATA_DIR / filename).read_bytes()).hexdigest() == expected
    assert data.catalogue_sha256 == BASELINE["icd_catalog.json"]
    assert data.guidelines_sha256 == BASELINE["guideline_snippets.json"]


@pytest.mark.parametrize("filename,field", [("icd_catalog.json", "code"), ("guideline_snippets.json", "id")])
@pytest.mark.parametrize("damage", ["duplicate", "count", "schema", "json"])
def test_loader_rejects_corrupt_corpus(tmp_path, filename, field, damage):
    for source in DATA_DIR.glob("*.json"):
        (tmp_path / source.name).write_bytes(source.read_bytes())
    target = tmp_path / filename
    records = json.loads(target.read_text())
    if damage == "duplicate":
        records[1][field] = records[0][field]
    elif damage == "count":
        records.pop()
    elif damage == "schema":
        records[0].pop("title")
    target.write_text("{" if damage == "json" else json.dumps(records))
    with pytest.raises(ValueError):
        load_supplied_data(tmp_path)


def run_cli(*args):
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    return subprocess.run([sys.executable, "-m", "app.main", *args], env=env,
                          capture_output=True, text=True)


def test_cli_help_and_no_key_self_check():
    help_result = run_cli("--help")
    assert help_result.returncode == 0
    assert "--check-data" in help_result.stdout
    checked = run_cli("--check-data", "--self-check")
    assert checked.returncode == 0
    assert "404 unique codes" in checked.stderr
    assert "45 unique IDs" in checked.stderr
    assert len(checked.stdout.splitlines()) == 1
    result = CodingResult.model_validate_json(checked.stdout)
    assert result.status == "unresolved" and not result.assignments
    assert result.original_note and result.unresolved
    assert result.provenance.model is None
    assert result.provenance.mode == "bootstrap"


def test_cli_bad_data_reports_stderr(tmp_path):
    result = run_cli("--check-data", "--data-dir", str(tmp_path))
    assert result.returncode == 1
    assert not result.stdout
    assert "Data validation failed" in result.stderr


def test_contract_rejects_missing_disposition_and_hypothesis_as_finding():
    with pytest.raises(ValidationError):
        Finding.model_validate(dict(finding_id="f", type="other", assertion="unclear",
                                    evidence=dict(source_type="note", source_id="n", source_quote="text")))
    with pytest.raises(ValidationError):
        Finding.model_validate(dict(text="hypothesis", rationale="non-evidentiary"))


def test_contract_origin_and_status():
    assignment = dict(code="structural-placeholder", catalogue_origin="supplied", finding_ids=["f"],
                      evidence=[dict(source_type="note", source_id="n", source_quote="text")],
                      certainty="definitive", confidence=dict(level="low"))
    with pytest.raises(ValidationError):
        Assignment.model_validate(dict(assignment, catalogue_origin="expanded"))
    data = load_supplied_data()
    base = dict(note_id="n", original_note="text", confidence=dict(level="low"),
                provenance=dict(mode="bootstrap", catalogue_sha256=data.catalogue_sha256,
                                guidelines_sha256=data.guidelines_sha256))
    for certainty, status in [("definitive", "coded"), ("provisional", "provisional")]:
        result = CodingResult.model_validate(dict(base, assignments=[dict(assignment, certainty=certainty)], status=status))
        assert result.status == status
    with pytest.raises(ValidationError):
        CodingResult.model_validate(dict(base, status="coded"))


def test_offsets_fact_provenance_and_immutable_note():
    with pytest.raises(ValidationError):
        Evidence(source_type="note", source_id="n", source_quote="text", start=2, end=1)
    with pytest.raises(ValidationError):
        ClinicalFact(kind="age_years", value=20, certainty="known", extraction_method="explicit_numeric")
    note = Note(note_id="n", text="unchanged")
    with pytest.raises(ValidationError):
        note.text = "replacement"
