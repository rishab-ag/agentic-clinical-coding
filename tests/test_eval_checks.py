"""Non-clinical dummy predicates and output evidence checks only."""
import pytest

from app.eval_checks import OutputPredicate, OutputCheck, evaluate_predicate, evaluate_check, predicate_schema_issues
from app.evaluation import grade_fixture, FixtureSet, load_fixtures
from test_evaluation import dummy_fixture, dummy_result, dummy_assignment, dummy_data


def test_recursive_output_selectors():
    predicate=OutputPredicate.model_validate(dict(path="assignments",operator="any",item=dict(all_of=[
        dict(path="code",operator="in",value=["DUMMY-A"]),dict(path="certainty",operator="eq",value="provisional")])))
    assert evaluate_predicate(predicate,dummy_result()) == "not_met"
    assert evaluate_predicate(predicate,dummy_result(assignments=[dummy_assignment(certainty="provisional")])) == "met"
    assert evaluate_predicate(OutputPredicate(path="not_a_field",operator="eq",value=True),{}) == "unknown"
    assert evaluate_predicate(OutputPredicate(path="value",operator="eq",value=True),{"value":1}) == "not_met"
    assert evaluate_predicate(OutputPredicate.model_validate(dict(path="assignments",operator="all",item=dict(path="code",operator="eq",value="DUMMY-A"))),dummy_result()) == "unknown"
    assert predicate_schema_issues(predicate)==[]
    wrong=OutputPredicate.model_validate(dict(path="assignments",operator="any",item=dict(path="assignment_status",operator="eq",value="provisional")))
    assert "assignment_status" in predicate_schema_issues(wrong)[0]


def test_executable_conditions_check_actual_certainty_and_original_note(dummy_data):
    fixture=dummy_fixture(acceptable_statuses=["provisional","unresolved"],conditional_expectations=[
        dict(when=dict(path="assignments",operator="any",item=dict(path="code",operator="eq",value="DUMMY-A")),checks=[
            dict(kind="predicate",predicate=dict(path="assignments",operator="all",item=dict(path="certainty",operator="eq",value="provisional"))),
            dict(kind="original_note_evidence")])])
    assert grade_fixture(fixture,dummy_result(),dummy_data)["passed"]
    raw=dummy_result(status="provisional",assignments=[dummy_assignment(certainty="provisional")])
    assert grade_fixture(fixture,raw,dummy_data)["passed"]
    raw["assignments"][0]["evidence"][0]["source_quote"]="ABSENT DUMMY TEXT"
    assert not grade_fixture(fixture,raw,dummy_data)["passed"]


def test_confirmed_encounter_link_uses_immutable_note():
    raw=dummy_result(assignments=[dummy_assignment()])
    raw["findings"]=[dict(finding_id="dummy-finding",assertion="confirmed",encounter_relevant=True,
        evidence=dict(source_type="note",source_id="dummy-1",source_quote="NON-CLINICAL SOFTWARE SENTINEL"))]
    check=OutputCheck(kind="confirmed_encounter_link")
    assert evaluate_check(check,raw,"dummy-1",raw["original_note"]) == "met"
    for assertion in ("historical","negated","suspected","patient_reported"):
        raw["findings"][0]["assertion"]=assertion
        assert evaluate_check(check,raw,"dummy-1",raw["original_note"]) == "not_met"
    raw["findings"][0]["assertion"]="confirmed"
    raw["findings"][0]["encounter_relevant"]=False
    assert evaluate_check(check,raw,"dummy-1",raw["original_note"]) == "not_met"


def test_unknown_trigger_is_failure_not_a_skipped_requirement(dummy_data):
    fixture=dummy_fixture(conditional_expectations=[dict(when=dict(path="assignment_status",operator="eq",value="provisional"),
        checks=[dict(kind="predicate",predicate=dict(path="status",operator="eq",value="unresolved"))])])
    report=grade_fixture(fixture,dummy_result(),dummy_data)
    assert not report["passed"] and "Unknown output path" in report["errors"][0]


def test_held_out_and_review_metadata_round_trip_unchanged(tmp_path,dummy_data):
    fixture=dummy_fixture(split="held_out",review_status="pending_human_review")
    path=tmp_path/"dummy.jsonl"
    path.write_text(fixture.model_dump_json()+"\n")
    baseline=path.read_bytes()
    loaded=load_fixtures(path,dummy_data).fixtures[0]
    assert loaded.split==fixture.split and loaded.reviewed_by==fixture.reviewed_by
    assert loaded.reviewed_at==fixture.reviewed_at and loaded.review_status==fixture.review_status
    assert path.read_bytes()==baseline


def test_review_packet_alias_and_nested_pending_metadata(tmp_path,dummy_data):
    import json
    payload=dummy_fixture(review_status="pending_human_review").model_dump()
    payload.pop("split")
    payload["evaluation_split"]="held_out"
    payload["review_metadata"]={"reviewer":None,"reviewed_at":None,"review_status":"pending_human_review","review_notes":"NONCLINICAL DUMMY REVIEW"}
    path=tmp_path/"dummy-packet.jsonl"
    path.write_text(json.dumps(payload)+"\n")
    baseline=path.read_bytes()
    loaded=load_fixtures(path,dummy_data).fixtures[0]
    assert loaded.split=="held_out" and loaded.review_metadata.model_dump()==payload["review_metadata"]
    assert loaded.review_status=="pending_human_review" and path.read_bytes()==baseline
