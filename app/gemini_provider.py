"""Bounded Gemini generateContent REST adapter; credentials never enter URLs."""
from dataclasses import replace
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from app.ingestion import _json
from app.model_provider import (NoRedirect, ModelFailure, MalformedOutput,
                                ContextOverflow, ModelReply)


def payload_for(config,messages,schema):
    systems=[m['content'] for m in messages if m['role']=='system']
    contents=[dict(role='model' if m['role']=='assistant' else 'user',parts=[dict(text=m['content'])])
              for m in messages if m['role']!='system']
    return dict(systemInstruction=dict(parts=[dict(text='\n'.join(systems))]),contents=contents,
                generationConfig=dict(maxOutputTokens=config.max_output_tokens,
                    responseFormat=dict(text=dict(mimeType='application/json',schema=schema))))


class GeminiModel:
    provider='gemini'
    def __init__(self,config,transport=None,sleep=time.sleep):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',config.model):
            raise ValueError('Gemini model must be a model ID, not a URL')
        self.config=config
        self.transport=transport or build_opener(NoRedirect()).open
        self.sleep=sleep

    def prompt_bound(self,messages,schema,name=None):
        return len(json.dumps(payload_for(self.config,messages,schema),ensure_ascii=False).encode())+1024

    def extract(self,messages,schema):return self._call(messages,schema)
    def decide(self,messages,schema):return self._call(messages,schema)
    def repair(self,messages,schema):
        return GeminiModel(replace(self.config,retries=0),self.transport,self.sleep)._call(messages,schema)

    def _call(self,messages,schema):
        if self.prompt_bound(messages,schema)+self.config.max_output_tokens>self.config.context_limit:
            raise ContextOverflow('Full Gemini context exceeds configured limit')
        request=Request('https://generativelanguage.googleapis.com/v1beta/models/'+self.config.model+':generateContent',
            data=json.dumps(payload_for(self.config,messages,schema)).encode(),
            headers={'x-goog-api-key':self.config.api_key,'Content-Type':'application/json'},method='POST')
        start=time.monotonic()
        for attempt in range(self.config.retries+1):
            tokens=None
            def failure(message):
                return ModelFailure(message,attempt,(time.monotonic()-start)*1000,
                                    tokens if type(tokens) is int and tokens>=0 else None)
            try:
                with self.transport(request,timeout=self.config.timeout) as response:
                    body=_json(response.read().decode('utf-8'))
                tokens=body.get('usageMetadata',{}).get('promptTokenCount')
                candidates=body.get('candidates',[])
                if body.get('promptFeedback',{}).get('blockReason') or len(candidates)!=1:
                    raise failure('Gemini blocked or missing unique response')
                candidate=candidates[0]
                if candidate.get('finishReason')!='STOP':
                    raise failure('Gemini response incomplete or refused')
                parts=candidate.get('content',{}).get('parts',[])
                text=''.join(p['text'] for p in parts if 'text' in p and not p.get('thought',False))
                if not text or type(tokens) is not int or tokens<0:
                    raise failure('Gemini output/token usage missing')
                if tokens+self.config.max_output_tokens>self.config.context_limit:
                    raise ContextOverflow('Actual Gemini token usage exceeds reserve',attempt,(time.monotonic()-start)*1000,tokens)
                try: payload=_json(text)
                except ValueError:
                    raise MalformedOutput(text,attempt,(time.monotonic()-start)*1000,tokens) from None
                return ModelReply(payload,tokens,attempt,(time.monotonic()-start)*1000)
            except HTTPError as error:
                if error.code not in (408,409,429) and not 500<=error.code<=599 or attempt==self.config.retries:
                    raise failure('Gemini HTTP request failed') from None
            except (URLError,TimeoutError):
                if attempt==self.config.retries:raise failure('Gemini transport failed') from None
            except (ValueError,TypeError,KeyError,AttributeError):
                raise failure('Invalid Gemini response') from None
            self.sleep(min(.5*2**attempt,2))
