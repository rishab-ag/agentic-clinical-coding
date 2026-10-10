"""External infrastructure tests use non-clinical dummy human-review metadata.

Dummy approvals simulate trusted input; no clinical source is approved here.
"""
import hashlib,json
from copy import deepcopy
from pathlib import Path
import pytest
from app.expansion import ExternalEntry, load_expansion, entry_digest, DEFAULT_MANIFEST
from app.data import load_supplied_data
from app.pipeline import NoKeyPipeline
from app.reasoning import ModelPipeline
from app.models import Note
from app.ingestion import InputRecord
from test_model_reasoning import data, FakeModel, decision, record, extraction

def dummy(kind='catalogue'):
    title='NONCLINICAL EXTERNAL SENTINEL'
    fragment=('EXTERNAL_DUMMY '+title) if kind=='catalogue' else title
    return dict(entry_id='EXT-DUMMY',kind=kind,code='EXTERNAL_DUMMY' if kind=='catalogue' else None,title=title,
        chapter='Nonclinical chapter' if kind=='catalogue' else None,text=fragment if kind=='guideline' else None,
        icd_uri='http://id.who.int/icd/entity/0' if kind=='catalogue' else None,
        source=dict(url='https://example.invalid/dummy',publisher='Nonclinical dummy publisher',accessed_date='2026-10-10',
            version='dummy',locator='dummy section',fragment=fragment,fragment_sha256=hashlib.sha256(fragment.encode()).hexdigest(),
            attribution_note='Nonclinical simulated permission',fetched_facts=['Dummy record only'],unverified_facts=[]),
        reason='Nonclinical structural sentinel',linked_supplied_guideline_ids=['S0'])

def save(tmp_path,entries):
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps(dict(schema_version='external-proposals-v1',entries=entries)))
    return path

def reviewed(item):
    entry=ExternalEntry.model_validate(item)
    return dict(item,review_status='human_approved',review=dict(reviewer='DUMMY TEST SIMULATION',reviewed_at='2000-01-01',
        payload_sha256=entry_digest(entry),exact_mapping_checked=True,source_checked=True,reuse_permission_checked=True,note='Nonclinical test only'))

def test_actual_manifest_activates_only_the_source_checked_code():
    supplied=load_supplied_data()
    manifest,digest=load_expansion(supplied)
    assert {e.entry_id:e.review_status for e in manifest.entries}=={
        'EXT-ICD-NF':'human_approved','EXT-GUIDE-SKIN-REFERRAL':'pending_human_review'}
    pipeline=NoKeyPipeline(supplied)
    assert list(pipeline.expanded_catalogue)==['1B71'] and pipeline.expanded_guidelines=={}
    assert '1B71' not in pipeline.catalogue
    assert pipeline.provenance().expansion_sha256==digest

@pytest.mark.parametrize('kind',['catalogue','guideline'])
def test_unreviewed_records_excluded(data,tmp_path,kind):
    pipeline=NoKeyPipeline(data,expansion_path=save(tmp_path,[dummy(kind)]))
    assert not pipeline.expanded_catalogue and not pipeline.expanded_guidelines

@pytest.mark.parametrize('change',['hash','approval','reuse','stale','duplicate','collision','linkage','excerpt'])
def test_invalid_manifest_rejected(data,tmp_path,change):
    item=reviewed(dummy()); entries=[item]
    if change=='hash': item['source']['fragment']='altered'
    if change=='approval': item['review']=None
    if change=='reuse': item['review']['reuse_permission_checked']=False
    if change=='stale': item['title']='altered'
    if change=='duplicate': entries.append(deepcopy(item))
    if change=='collision':
        item=dummy();item['code']='D0';item['source']['fragment']='D0 NONCLINICAL EXTERNAL SENTINEL'
        item['source']['fragment_sha256']=hashlib.sha256(item['source']['fragment'].encode()).hexdigest();entries=[item]
    if change=='linkage': item=dummy();item['linked_supplied_guideline_ids']=['ABSENT'];entries=[item]
    if change=='excerpt': item=dummy('guideline');item['text']='ABSENT';entries=[item]
    with pytest.raises(ValueError): load_expansion(data,save(tmp_path,entries))

def test_reviewed_external_retrieval_keeps_origin_and_refuses(data,tmp_path):
    path=save(tmp_path,[reviewed(dummy())])
    pipeline=NoKeyPipeline(data,expansion_path=path)
    note=InputRecord(note=Note(note_id='dummy',text='NONCLINICAL EXTERNAL SENTINEL'),position=1,original_record='dummy')
    result=pipeline.process(note)
    external=next(c for c in result.candidates_considered if c.catalogue_origin=='expanded')
    assert external.code=='EXTERNAL_DUMMY' and external.status=='unresolved'
    assert external.source=='https://example.invalid/dummy'
    assert result.status=='unresolved' and not result.assignments
    assert 'Expanded-only' in ' '.join(result.warnings)

def test_expanded_assignment_can_never_be_promoted(data,tmp_path):
    proposed=decision(True);proposed['assignments'][0]['code']='EXTERNAL_DUMMY'
    proposed['assignments'][0]['catalogue_origin']='expanded'
    result=ModelPipeline(data,FakeModel(decide=proposed),expansion_path=save(tmp_path,[reviewed(dummy())])).process(record())
    assert result.status=='unresolved' and not result.assignments

def test_reviewed_candidate_is_canonicalized(data,tmp_path):
    proposed=decision(); proposed['candidates_considered']=[dict(code='EXTERNAL_DUMMY',title='NONCLINICAL EXTERNAL SENTINEL',catalogue_origin='expanded',status='unresolved',source='https://example.invalid/false',reason='dummy')]
    pipeline=ModelPipeline(data,FakeModel(decide=proposed),expansion_path=save(tmp_path,[reviewed(dummy())]))
    result=pipeline.process(record())
    assert next(c for c in result.candidates_considered if c.catalogue_origin=='expanded').source=='https://example.invalid/dummy'

def test_external_guideline_requires_separate_applicability(data,tmp_path):
    model=FakeModel(decide=decision(True))
    result=ModelPipeline(data,model,expansion_path=save(tmp_path,[reviewed(dummy('guideline'))])).process(record())
    assert result.status=='unresolved' and not result.assignments
    assert 'EXT-DUMMY' in model.calls[1][1][1]['content']

def test_output_cannot_overwrite_manifest(tmp_path,capsys):
    from app.main import main
    assert main(['--input','examples/messy_note.txt','--output',str(DEFAULT_MANIFEST),'--no-model'])==1
    assert 'external source' in capsys.readouterr().err

def test_activated_code_surfaces_only_for_matching_notes_and_never_assigns():
    pipeline=NoKeyPipeline(load_supplied_data())
    def run(text):
        return pipeline.process(InputRecord(note=Note(note_id='n',text=text),position=1,original_record=text))
    unrelated=run(Path('examples/vitiligo_note.txt').read_text())
    assert all(c.catalogue_origin=='supplied' for c in unrelated.candidates_considered)
    matching=run('SYNTHETIC. Surgeon confirms necrotising fasciitis of the leg.')
    hit=[c for c in matching.candidates_considered if c.catalogue_origin=='expanded']
    assert [c.code for c in hit]==['1B71'] and hit[0].status=='unresolved'
    assert matching.status=='unresolved' and not matching.assignments
    assert any('Expanded-only candidate 1B71' in w for w in matching.warnings)
