"""Structural proposal checks and clearly non-clinical dummy regression outputs.

No clinical fixture is approved or clinically scored by these tests.
"""
import json
from pathlib import Path
from app.evaluation import load_fixtures, grade_fixture
from app.data import load_supplied_data
from app.eval_checks import ExecutableConditionalExpectation, conditional_schema_issues
from test_evaluation import dummy_fixture, dummy_result, dummy_assignment, dummy_data

ROOT=Path(__file__).resolve().parents[1]

def proposed(note_id):
    packet=json.loads((ROOT/'docs/fixture_expectation_proposals.json').read_text())
    return next(p['proposed_conditions'] for p in packet['proposals'] if p['note_id']==note_id)

def nonclinical_conditions():
    # Substitute every proposed selector with NONCLINICAL sentinel IDs. This tests
    # predicate semantics, not whether the clinical mapping is correct.
    def convert(value):
        if isinstance(value,list): return [convert(v) for v in value]
        if isinstance(value,dict): return {k:convert(v) for k,v in value.items()}
        if value in ['CA22','CA23','CA24','CA25']: return 'DUMMY-A'
        if value=='GDL-016': return 'DUMMY-SOURCE'
        return value
    return convert(proposed('E02'))

def test_proposals_are_executable_with_consistent_review_metadata():
    fixtures=load_fixtures(ROOT/'tests/fixtures/clinical_eval.jsonl',load_supplied_data()).fixtures
    for f in fixtures:
        if f.note_id not in {'E02','E03','E04','E05','E07','E10'}: continue
        assert f.review_metadata.review_status==f.review_status
        assert f.review_status in {'pending_human_review','human_approved'}
        assert all(isinstance(c,ExecutableConditionalExpectation) and not conditional_schema_issues(c)
                   for c in f.conditional_expectations)

def test_selected_provisional_assignment_checks_nonclinical_only(dummy_data):
    fixture=dummy_fixture(acceptable_statuses=['provisional','unresolved'],conditional_expectations=nonclinical_conditions())
    assignment=dummy_assignment(certainty='provisional');assignment['guideline_ids']=['DUMMY-SOURCE']
    raw=dummy_result(status='provisional',assignments=[assignment])
    assert grade_fixture(fixture,raw,dummy_data)['passed']
    assignment['confidence']['level']='high'
    assert not grade_fixture(fixture,raw,dummy_data)['passed']
    assignment['confidence']['level']='low';assignment['guideline_ids']=[]
    assert not grade_fixture(fixture,raw,dummy_data)['passed']
    assignment['guideline_ids']=['DUMMY-SOURCE'];assignment['certainty']='definitive';raw['status']='coded'
    assert not grade_fixture(fixture,raw,dummy_data)['passed']

def test_refusal_candidate_missing_information_nonclinical_only(dummy_data):
    fixture=dummy_fixture(conditional_expectations=nonclinical_conditions())
    raw=dummy_result()
    assert not grade_fixture(fixture,raw,dummy_data)['passed']
    raw['candidates_considered']=[dict(code='DUMMY-A',title='NONCLINICAL SENTINEL',catalogue_origin='supplied',
        source='unit test',status='unresolved',reason='Nonclinical dummy explanation',missing_discriminators=['Missing imaging'])]
    assert grade_fixture(fixture,raw,dummy_data)['passed']
    raw['candidates_considered'][0]['missing_discriminators']=[]
    assert not grade_fixture(fixture,raw,dummy_data)['passed']
