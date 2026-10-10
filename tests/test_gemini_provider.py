"""Mocked nonclinical Gemini transport checks; no paid/live requests."""
import io,json
from urllib.error import HTTPError
import pytest
from app.gemini_provider import GeminiModel
from app.model_provider import ModelConfig,ModelFailure,MalformedOutput,ContextOverflow,model_from_environment

def response(text='{"dummy":true}',finish='STOP',tokens=20):
    return io.BytesIO(json.dumps(dict(candidates=[dict(finishReason=finish,content=dict(parts=[dict(text=text)]))],usageMetadata=dict(promptTokenCount=tokens))).encode())

def test_gemini_request_contract_and_usage():
    calls=[]
    def transport(request,timeout):
        calls.append(request);return response()
    model=GeminiModel(ModelConfig('NONSECRET_DUMMY','dummy-model',1000000),transport=transport)
    result=model.extract([dict(role='system',content='trusted dummy'),dict(role='user',content='untrusted dummy')],{'type':'object'})
    assert result.payload=={'dummy':True} and result.input_tokens==20
    request=calls[0];body=json.loads(request.data)
    assert 'NONSECRET_DUMMY' not in request.full_url and 'NONSECRET_DUMMY' not in str(body)
    assert request.get_header('X-goog-api-key')=='NONSECRET_DUMMY'
    assert body['systemInstruction']['parts'][0]['text']=='trusted dummy'
    assert body['generationConfig']['responseMimeType']=='application/json'
    assert body['generationConfig']['responseJsonSchema']=={'type':'object'}
    assert 'responseFormat' not in body['generationConfig']

@pytest.mark.parametrize('finish',['MAX_TOKENS','SAFETY','RECITATION'])
def test_incomplete_or_refused_output_never_accepted(finish):
    model=GeminiModel(ModelConfig('dummy','dummy',1000000),transport=lambda *a,**k:response(finish=finish))
    with pytest.raises(ModelFailure):model.decide([], {})

def test_malformed_output_is_repairable_not_retried():
    calls=[]
    def transport(*a,**k):calls.append(1);return response(text='{')
    model=GeminiModel(ModelConfig('dummy','dummy',1000000),transport=transport)
    with pytest.raises(MalformedOutput):model.decide([], {})
    assert len(calls)==1

def test_repair_has_one_request_and_sanitizes_http_errors():
    calls=[]
    def transport(request,timeout):
        calls.append(1);raise HTTPError(request.full_url,429,'SECRET',{},None)
    model=GeminiModel(ModelConfig('dummy','dummy',1000000,retries=2),transport=transport)
    with pytest.raises(ModelFailure) as error:model.repair([], {})
    assert len(calls)==1 and 'SECRET' not in str(error.value)

def test_context_limit_prevents_requests():
    model=GeminiModel(ModelConfig('dummy','dummy',5000),transport=lambda *a,**k:pytest.fail('must not send'))
    with pytest.raises(ContextOverflow):model.extract([dict(role='user',content='x'*5000)],{})

def test_environment_selects_gemini_without_showing_key(monkeypatch):
    monkeypatch.setenv('MODEL_PROVIDER','gemini');monkeypatch.setenv('GEMINI_API_KEY','NONSECRET_DUMMY')
    monkeypatch.setenv('GEMINI_MODEL','dummy');monkeypatch.setenv('GEMINI_CONTEXT_LIMIT','1000000')
    assert isinstance(model_from_environment(),GeminiModel)
    monkeypatch.delenv('GEMINI_API_KEY');assert model_from_environment() is None

def test_transient_retry_is_bounded():
    calls=[]
    def transport(request,timeout):
        calls.append(1)
        if len(calls)==1:raise HTTPError(request.full_url,503,'dummy',{},None)
        return response()
    model=GeminiModel(ModelConfig('dummy','dummy',1000000),transport=transport,sleep=lambda _:None)
    assert model.extract([],{}).retries==1 and len(calls)==2

# Same nonclinical corpus and extraction/decision sentinels used by the existing
# provider-independent reasoning tests. No real Google responses are claimed.
from test_model_reasoning import data,record,extraction,decision
from app.reasoning import ModelPipeline

@pytest.mark.parametrize('repair',[False,True])
def test_gemini_two_stage_pipeline_and_single_repair(data,repair):
    proposed=decision(True)
    if repair:proposed['dispositions']=[]
    payloads=[extraction(),proposed]+([decision(True)] if repair else [])
    calls=[]
    def transport(request,timeout):
        calls.append(json.loads(request.data))
        return response(text=json.dumps(payloads[len(calls)-1]))
    model=GeminiModel(ModelConfig('NONSECRET_DUMMY','dummy',1000000),transport=transport)
    result=ModelPipeline(data,model).process(record())
    assert result.status=='coded' and result.provenance.provider=='gemini'
    assert result.provenance.model_repairs==int(repair)
    assert len(calls)==2+int(repair)
    stage_two=json.loads(calls[1]['contents'][0]['parts'][0]['text'].split('\n',1)[1].rsplit('\n',1)[0])
    assert len(stage_two['supplied_catalogue'].splitlines())==404 and len(stage_two['guidelines'])==45

def test_http_400_has_safe_status_and_reason_without_error_body():
    body=json.dumps({'error':{'message':'SECRET_RESPONSE', 'details':[{'reason':'API_KEY_INVALID'}]}}).encode()
    def transport(request,timeout):
        raise HTTPError(request.full_url,400,'SECRET_KEY',{},io.BytesIO(body))
    model=GeminiModel(ModelConfig('dummy','dummy',1000000),transport=transport)
    with pytest.raises(ModelFailure) as error:model.extract([],{})
    assert 'status 400' in str(error.value) and 'API_KEY_INVALID' in str(error.value)
    assert 'SECRET' not in str(error.value)

@pytest.mark.parametrize('retry_count',[0,1])
def test_socket_timeout_is_bounded_and_accounts_for_latency(retry_count):
    import socket
    calls=[]
    def transport(request,timeout):
        calls.append(1)
        raise socket.timeout('NONCLINICAL_UNTRUSTED_EXCEPTION')
    model=GeminiModel(ModelConfig('dummy','dummy',1000000,timeout=120,retries=retry_count),transport=transport,sleep=lambda _:None)
    with pytest.raises(ModelFailure) as error:model.extract([],{})
    assert 'timed out' in str(error.value)
    assert 'NONCLINICAL_UNTRUSTED_EXCEPTION' not in str(error.value)
    assert error.value.retries==retry_count and error.value.latency_ms>0
    assert len(calls)==retry_count+1


def test_gemini_key_alone_configures_a_usable_model(monkeypatch):
    from app.model_provider import model_from_environment, GEMINI_DEFAULTS
    for name in ('MODEL_PROVIDER','OPENAI_API_KEY','GEMINI_MODEL','GEMINI_CONTEXT_LIMIT','GEMINI_MAX_OUTPUT_TOKENS','GEMINI_TIMEOUT_SECONDS','GEMINI_RETRIES'):
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('GEMINI_API_KEY','NONSECRET_DUMMY_KEY')
    config=model_from_environment().config
    assert (config.model,str(config.context_limit))==GEMINI_DEFAULTS
    assert config.max_output_tokens==16384 and config.timeout==120
    monkeypatch.setenv('GEMINI_MODEL','dummy-model');monkeypatch.setenv('GEMINI_MAX_OUTPUT_TOKENS','')
    assert model_from_environment().config.model=='dummy-model'
