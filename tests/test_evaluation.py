"""Non-clinical dummy records test runner mechanics, never clinical quality.

Sentinel codes/sources below are invented software identifiers, not ICD-11
entries, clinical labels, independent human review, or evaluation fixtures.
"""
import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.data import CatalogueEntry, GuidelineSnippet, SuppliedData
from app.evaluation import (FixtureSet, HumanFixture, evaluate_callable, evaluate_results,
                            grade_fixture, load_fixtures, read_result_lines, main)


@pytest.fixture
def dummy_data():
    return SuppliedData(catalogue=[CatalogueEntry(code=key,title="NON-CLINICAL SOFTWARE SENTINEL",chapter="dummy",synonyms=[])
                                   for key in ("DUMMY-A","DUMMY-B")],
        guidelines=[GuidelineSnippet(id="DUMMY-SOURCE",title="NON-CLINICAL SOFTWARE SOURCE",source="unit test",effective="2000-01",text="Dummy text")],
        catalogue_sha256="0"*64,guidelines_sha256="1"*64)


def dummy_fixture(**changes):
    payload = dict(note_id="dummy-1",note_text="NON-CLINICAL SOFTWARE SENTINEL",acceptable_statuses=["unresolved"],
                   required_codes=[],forbidden_codes=[],relevant_guideline_ids=[],review_status="human_approved",
                   reviewed_by="NONCLINICAL_TEST_ONLY",reviewed_at="2000-01-01T00:00:00Z",
                   rationale="Dummy rubric for unit testing only; not actual independent clinical review",coverage_tags=["software-only"])
    payload.update(changes)
    return HumanFixture.model_validate(payload)


def dummy_result(**changes):
    payload = dict(note_id="dummy-1",original_note="NON-CLINICAL SOFTWARE SENTINEL",status="unresolved",assignments=[],
                   unresolved=["Dummy explanation"],confidence=dict(level="low"),
                   provenance=dict(mode="bootstrap",catalogue_sha256="0"*64,guidelines_sha256="1"*64))
    payload.update(changes)
    return payload


def dummy_assignment(code="DUMMY-A",certainty="definitive"):
    return dict(code=code,catalogue_origin="supplied",finding_ids=["dummy-finding"],certainty=certainty,
                evidence=[dict(source_type="note",source_id="dummy-1",source_quote="NON-CLINICAL SOFTWARE SENTINEL")],
                confidence=dict(level="low"))


def test_load_fixture_contract_and_multiple_acceptable_statuses(tmp_path,dummy_data):
    fixture = dummy_fixture(acceptable_statuses=["coded","unresolved"])
    path = tmp_path/"dummy-fixtures.json"
    path.write_text(FixtureSet(fixtures=[fixture]).model_dump_json())
    loaded = load_fixtures(path,dummy_data)
    assert grade_fixture(loaded.fixtures[0],dummy_result(),dummy_data)["passed"]
    assert grade_fixture(loaded.fixtures[0],dummy_result(status="coded",assignments=[dummy_assignment()]),dummy_data)["passed"]


def test_subset_required_codes_and_optional_exact_alternatives(dummy_data):
    fixture = dummy_fixture(acceptable_statuses=["coded"],required_codes=["DUMMY-A"])
    assert grade_fixture(fixture,dummy_result(status="coded",assignments=[dummy_assignment(),dummy_assignment("DUMMY-B")]),dummy_data)["passed"]
    assert not grade_fixture(fixture,dummy_result(status="coded",assignments=[dummy_assignment("DUMMY-B")]),dummy_data)["passed"]
    fixture = dummy_fixture(acceptable_statuses=["coded","unresolved"],acceptable_outcomes=[
        dict(status="coded",allowed_code_sets=[["DUMMY-A"],["DUMMY-B"]]),dict(status="unresolved")])
    for raw in [dummy_result(),dummy_result(status="coded",assignments=[dummy_assignment()]),
                dummy_result(status="coded",assignments=[dummy_assignment("DUMMY-B")])]:
        assert grade_fixture(fixture,raw,dummy_data)["passed"]
    assert not grade_fixture(fixture,dummy_result(status="coded",assignments=[dummy_assignment(),dummy_assignment("DUMMY-B")]),dummy_data)["passed"]


def test_conditional_requirements_only_apply_to_triggered_outcome(dummy_data):
    fixture = dummy_fixture(acceptable_statuses=["coded","unresolved"],conditional_expectations=[
        dict(when_status="coded",required_codes=["DUMMY-A"]),
        dict(when_status="unresolved",required_explanations=["dummy explanation"]),
        dict(when_all_codes=["DUMMY-A"],forbidden_codes=["DUMMY-B"])])
    assert grade_fixture(fixture,dummy_result(),dummy_data)["passed"]
    assert grade_fixture(fixture,dummy_result(status="coded",assignments=[dummy_assignment()]),dummy_data)["passed"]
    assert not grade_fixture(fixture,dummy_result(status="coded",assignments=[dummy_assignment("DUMMY-B")]),dummy_data)["passed"]
    assert not grade_fixture(fixture,dummy_result(status="coded",assignments=[dummy_assignment(),dummy_assignment("DUMMY-B")]),dummy_data)["passed"]
    assert not grade_fixture(fixture,dummy_result(unresolved=[]),dummy_data)["passed"]


def test_nonapproved_fixtures_never_scored_or_sent_to_callable(dummy_data):
    pending = dummy_fixture(note_id="pending",review_status="pending_review",acceptable_statuses=[],reviewed_by=None,reviewed_at=None,rationale=None)
    rejected = dummy_fixture(note_id="rejected",review_status="rejected")
    with pytest.raises(ValueError,match="Only human_approved"):
        grade_fixture(pending,dummy_result(),dummy_data)
    with pytest.raises(ValueError,match="No human_approved"):
        evaluate_results([pending,rejected],[],dummy_data)
    report = evaluate_results([dummy_fixture(),pending,rejected],[dummy_result()],dummy_data)
    assert report["passed"] and report["unscored_fixture_ids"] == ["pending","rejected"]
    calls = []
    def pipeline(note):
        calls.append(note.note_id)
        return dummy_result()
    report = evaluate_callable([dummy_fixture(),pending,rejected],pipeline,dummy_data)
    assert report["passed"] and calls == ["dummy-1"]


def test_jsonl_pending_prose_is_preserved_and_never_scored(tmp_path,dummy_data):
    payload = dummy_fixture().model_dump()
    payload.update(review_status="pending_human_review",title="NONCLINICAL DUMMY TITLE",
                   catalogue_basis="Dummy source",review_rationale="Unreviewed software-only draft",
                   conditional_expectations=[{"if":"DUMMY NONCLINICAL CONDITION","then":"DUMMY NONCLINICAL EXPECTATION"}])
    path = tmp_path/"dummy.jsonl"
    path.write_text(json.dumps(payload)+"\n")
    fixtures = load_fixtures(path,dummy_data)
    assert fixtures.fixtures[0].conditional_expectations[0].if_text == "DUMMY NONCLINICAL CONDITION"
    with pytest.raises(ValueError,match="No human_approved"):
        evaluate_results(fixtures.fixtures,[],dummy_data)
    with pytest.raises(ValidationError,match="conditional prose"):
        HumanFixture.model_validate(dict(payload,review_status="human_approved"))


@pytest.mark.parametrize("changes", [dict(reviewed_by=None),dict(acceptable_statuses=[]),
    dict(required_codes=["DUMMY-A"],forbidden_codes=["DUMMY-A"]),
    dict(expected_findings=[dict(source_quote="invented absent text",assertion="unclear",allowed_dispositions=["unresolved"])]),
    dict(conditional_expectations=[dict(required_codes=["DUMMY-A"])])])
def test_schema_rejects_missing_review_or_inconsistent_rubric(changes):
    with pytest.raises(ValidationError): dummy_fixture(**changes)


def test_duplicate_fixture_ids_and_unknown_reference_codes(tmp_path,dummy_data):
    with pytest.raises(ValidationError): FixtureSet(fixtures=[dummy_fixture(),dummy_fixture()])
    for fixture in [dummy_fixture(acceptable_statuses=["coded"],required_codes=["UNKNOWN"]),
                    dummy_fixture(relevant_guideline_ids=["UNKNOWN"]),
                    dummy_fixture(required_candidates=[dict(code="UNKNOWN",catalogue_origin="supplied")])]:
        path = tmp_path/"bad.json"
        path.write_text(FixtureSet(fixtures=[fixture]).model_dump_json())
        with pytest.raises(ValueError): load_fixtures(path,dummy_data)


@pytest.mark.parametrize("results", [[],[dummy_result(),dummy_result()],[None],
    [dummy_result(),dummy_result(note_id="unexpected")],[dict(note_id="dummy-1")]])
def test_missing_duplicate_extra_malformed_and_invalid_results_fail(results,dummy_data):
    assert not evaluate_results([dummy_fixture()],results,dummy_data)["passed"]


def test_partial_batch_exception_does_not_drop_second_case(dummy_data):
    cases = [dummy_fixture(),dummy_fixture(note_id="dummy-2")]
    def pipeline(note):
        if note.note_id == "dummy-1": raise RuntimeError("secret exception payload")
        return dummy_result(note_id=note.note_id)
    report = evaluate_callable(cases,pipeline,dummy_data)
    assert not report["passed"] and len(report["cases"]) == 2
    assert not report["cases"][0]["passed"] and report["cases"][1]["passed"]
    assert "secret exception payload" not in json.dumps(report)


def test_expected_findings_flags_candidates_citations_and_explanations(dummy_data):
    fixture = dummy_fixture(acceptable_statuses=["coded"],required_safety_flags=["DUMMY-FLAG"],
        expected_findings=[dict(source_quote="NON-CLINICAL SOFTWARE SENTINEL",assertion="unclear",allowed_dispositions=["unresolved","recorded_not_encounter"])],
        required_candidates=[dict(code="DUMMY-B",catalogue_origin="supplied",required_missing_discriminators=["DUMMY-DISCRIMINATOR"])],
        required_explanations=["dummy explanation"],required_guideline_ids=["DUMMY-SOURCE"])
    assignment = dummy_assignment()
    assignment["guideline_ids"] = ["DUMMY-SOURCE"]
    raw = dummy_result(status="coded",assignments=[assignment],safety_flags=["dummy-flag"],
        findings=[dict(finding_id="dummy-finding",type="other",assertion="unclear",disposition="unresolved",reason="Dummy explanation",
                       evidence=dict(source_type="note",source_id="dummy-1",source_quote="NON-CLINICAL SOFTWARE SENTINEL"))],
        candidates_considered=[dict(code="DUMMY-B",title="Dummy sentinel",catalogue_origin="supplied",source="unit test",status="unresolved",reason="Dummy reason",missing_discriminators=["DUMMY-DISCRIMINATOR"])])
    report = evaluate_results([fixture],[raw],dummy_data)
    assert report["passed"] and report["metrics"]["expected_finding_coverage"] == 1
    for field in ("safety_flags","findings","candidates_considered"):
        assert not grade_fixture(fixture,dict(raw,**{field:[]}),dummy_data)["passed"]
    assert not grade_fixture(fixture,dict(raw,assignments=[dummy_assignment()]),dummy_data)["passed"]


def test_original_note_cannot_supply_required_explanation(dummy_data):
    fixture = dummy_fixture(required_explanations=["non-clinical software sentinel"])
    assert not grade_fixture(fixture,dummy_result(),dummy_data)["passed"]


def test_forbidden_unknown_codes_citations_and_ungrounded_quotes_fail(dummy_data):
    raw = dummy_result(status="coded",assignments=[dummy_assignment()],confidence=dict(level="high"))
    fixture = dummy_fixture(acceptable_statuses=["coded"],forbidden_codes=["DUMMY-A"])
    report = evaluate_results([fixture],[raw],dummy_data)
    assert not report["passed"] and report["metrics"]["high_confidence_rubric_failures"] == 1
    fixture = dummy_fixture(acceptable_statuses=["coded"])
    for assignment in [dummy_assignment("UNKNOWN"),dict(dummy_assignment(),guideline_ids=["UNKNOWN"]),
        dict(dummy_assignment(),evidence=[dict(source_type="note",source_id="dummy-1",source_quote="absent quote")])]:
        assert not grade_fixture(fixture,dict(raw,assignments=[assignment]),dummy_data)["passed"]


def test_result_reader_accounts_for_blank_and_malformed_lines(tmp_path):
    path = tmp_path/"dummy.jsonl"
    path.write_text(json.dumps(dummy_result())+"\n\n{\n")
    results = read_result_lines(path)
    assert len(results) == 3 and results[1:] == [None,None]


def test_empty_template_cannot_pass_cli(tmp_path):
    path = tmp_path/"empty.jsonl"
    path.write_text("")
    result = subprocess.run([sys.executable,"-m","app.evaluation","--fixtures","eval/fixtures.template.json","--results",str(path)],capture_output=True,text=True)
    assert result.returncode == 2 and not result.stdout
    assert "human labels are required" in result.stderr


def test_cli_selects_development_and_keeps_gate_incomplete(tmp_path,dummy_data,monkeypatch,capsys):
    monkeypatch.setattr("app.evaluation.load_supplied_data",lambda:dummy_data)
    fixtures = tmp_path/"nonclinical-unit-fixtures.json"
    results = tmp_path/"dummy-results.jsonl"
    fixtures.write_text(FixtureSet(fixtures=[dummy_fixture(),dummy_fixture(note_id="dummy-2",split="held_out")]).model_dump_json())
    results.write_text(json.dumps(dummy_result())+"\n")
    assert main(["--fixtures",str(fixtures),"--results",str(results)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [c["note_id"] for c in report["cases"]] == ["dummy-1"]
    assert report["approved_fixture_count"] == 2 and not report["fixture_gate_met"]
    assert main(["--fixtures",str(fixtures),"--results",str(results),"--split","held_out"]) == 1
    held = json.loads(capsys.readouterr().out)
    assert not held["passed"] and held["cases"][0]["note_id"] == "dummy-2"


def test_cli_pending_fixtures_emit_skip_without_reading_results(tmp_path,dummy_data,monkeypatch,capsys):
    monkeypatch.setattr("app.evaluation.load_supplied_data",lambda:dummy_data)
    path=tmp_path/"pending-dummy.jsonl"
    fixture=dummy_fixture(review_status="pending_human_review")
    path.write_text(fixture.model_dump_json()+"\n")
    baseline=path.read_bytes()
    assert main(["--fixtures",str(path),"--results",str(tmp_path/"nonexistent-results")]) == 0
    report=json.loads(capsys.readouterr().out)
    assert report["status"] == "skipped" and report["passed"] is None and report["metrics"] is None
    assert report["clinical_scoring"] is False and not report["fixture_gate_met"]
    assert report["approved_fixture_count"] == 0 and report["unscored_fixture_ids"] == [fixture.note_id]
    assert main(["--fixtures",str(path),"--validate-fixtures"]) == 0
    validation=json.loads(capsys.readouterr().out)
    assert validation["status"] == "validated" and validation["clinical_scoring"] is False
    assert path.read_bytes() == baseline


def test_approved_scoring_requires_results_and_validation_is_unscored(tmp_path,dummy_data,monkeypatch,capsys):
    monkeypatch.setattr("app.evaluation.load_supplied_data",lambda:dummy_data)
    path=tmp_path/"approved-dummy.jsonl"
    path.write_text(dummy_fixture().model_dump_json()+"\n")
    assert main(["--fixtures",str(path)]) == 2
    assert "--results is required" in capsys.readouterr().err
    assert main(["--fixtures",str(path),"--validate-fixtures"]) == 0
    report=json.loads(capsys.readouterr().out)
    assert report["clinical_scoring"] is False


@pytest.mark.parametrize("opt_in,key,reason", [(False,None,"disabled"),(True,None,"absent"),(True,"NONSECRET_DUMMY_KEY","not configured")])
def test_live_stub_skips_honestly_without_calls(opt_in,key,reason):
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY",None)
    env.pop("OPENAI_MODEL",None)
    env.pop("OPENAI_CONTEXT_LIMIT",None)
    if key: env["OPENAI_API_KEY"] = key
    args = [sys.executable,"-m","app.live_eval"] + (["--live"] if opt_in else [])
    result = subprocess.run(args,capture_output=True,text=True,env=env)
    report = json.loads(result.stdout)
    assert result.returncode == 0 and report["status"] == "skipped" and report["model_calls"] == 0
    assert reason in report["reason"]
    assert "NONSECRET_DUMMY_KEY" not in result.stdout
