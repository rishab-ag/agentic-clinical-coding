"""Bounded OpenAI Responses REST adapter; no SDK/model downloads required."""
from dataclasses import dataclass, field
import json
import os
import time
import socket
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from app.ingestion import _json


class ModelFailure(Exception):
    """Safe application error; never includes HTTP response text or credentials."""
    def __init__(self,message,retries=0,latency_ms=0,input_tokens=None):
        super().__init__(message)
        self.retries,self.latency_ms,self.input_tokens=retries,latency_ms,input_tokens


class ContextOverflow(ModelFailure):
    pass


class MalformedOutput(ModelFailure):
    """Untrusted output retained solely for bounded structural repair."""
    def __init__(self, text, retries, latency_ms, input_tokens):
        super().__init__("Malformed model JSON", retries, latency_ms, input_tokens)
        self.payload=text


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        return None


@dataclass(frozen=True)
class ModelConfig:
    api_key: str = field(repr=False)
    model: str
    context_limit: int
    max_output_tokens: int = 4096
    timeout: float = 30
    retries: int = 1
    concurrency: int = 1

    def __post_init__(self):
        if not self.api_key or not self.model or not 1 <= self.concurrency <= 4:
            raise ValueError("Model configuration incomplete or invalid")
        if not 1 <= self.max_output_tokens < self.context_limit or not 0 < self.timeout <= 120 or not 0 <= self.retries <= 2:
            raise ValueError("Model bounds invalid")


@dataclass
class ModelReply:
    payload: Any
    input_tokens: int
    retries: int
    latency_ms: float


class ClinicalModel(Protocol):
    config: ModelConfig
    def extract(self, messages, schema) -> ModelReply: ...
    def decide(self, messages, schema) -> ModelReply: ...
    def repair(self, messages, schema) -> ModelReply: ...


def strict_schema(model):
    """Require every wire property (nullable optional values), validate fully locally."""
    schema = model.model_json_schema()
    def visit(value):
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                value["required"] = list(value.get("properties", {}))
                value["additionalProperties"] = False
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit(schema)
    return schema


def payload_for(config, messages, schema, name):
    return dict(model=config.model, input=messages, store=False, truncation="disabled",
                max_output_tokens=config.max_output_tokens,
                text={"format": {"type":"json_schema", "name":name, "strict":True, "schema":schema}})


def prompt_upper_bound(config, messages, schema, name):
    # Conservative operational bound over UTF-8 request bytes, plus framing reserve.
    # This is explicitly not a tokenizer measurement or a model-window claim.
    payload = payload_for(config, messages, schema, name)
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024


class OpenAIModel:
    def __init__(self, config, transport=None, sleep=time.sleep):
        self.config, self.transport, self.sleep = config, transport or build_opener(NoRedirect()).open, sleep

    def extract(self, messages, schema):
        return self._call(messages, schema, "clinical_extraction")

    def decide(self, messages, schema):
        return self._call(messages, schema, "clinical_decision")

    def repair(self, messages, schema):
        # Repair has no transport retries: exactly one bounded request.
        from dataclasses import replace
        return OpenAIModel(replace(self.config, retries=0), self.transport, self.sleep)._call(
            messages, schema, "clinical_decision")

    def _call(self, messages, schema, name):
        if prompt_upper_bound(self.config,messages,schema,name) + self.config.max_output_tokens > self.config.context_limit:
            raise ContextOverflow("Full context does not fit configured limit")
        request = Request("https://api.openai.com/v1/responses",
            data=json.dumps(payload_for(self.config,messages,schema,name)).encode("utf-8"),
            headers={"Authorization":"Bearer " + self.config.api_key,"Content-Type":"application/json"},method="POST")
        started = time.monotonic()
        for attempt in range(self.config.retries + 1):
            tokens=None
            def failure(message):
                return ModelFailure(message,attempt,(time.monotonic()-started)*1000,
                                    tokens if type(tokens) is int and tokens>=0 else None)
            try:
                with self.transport(request, timeout=self.config.timeout) as response:
                    body = _json(response.read().decode("utf-8"))
                tokens = body.get("usage", {}).get("input_tokens")
                if body.get("status") != "completed":
                    raise failure("Model response incomplete or refused")
                texts = []
                for item in body.get("output", []):
                    for content in item.get("content", []):
                        if content.get("type") == "refusal":
                            raise failure("Model refused")
                        if content.get("type") == "output_text":
                            texts.append(content["text"])
                tokens = body.get("usage", {}).get("input_tokens")
                if type(tokens) is not int or tokens < 0 or not texts:
                    raise failure("Missing output or token usage")
                # Schema parsing is local; malformed output is not retried into certainty.
                try:
                    payload = _json("".join(texts))
                except ValueError:
                    raise MalformedOutput("".join(texts),attempt,(time.monotonic()-started)*1000,tokens) from None
                return ModelReply(payload,tokens,attempt,(time.monotonic()-started)*1000)
            except HTTPError as error:
                retryable = error.code in (408,409,429) or 500 <= error.code <= 599
                if not retryable or attempt == self.config.retries:
                    raise failure("OpenAI HTTP request failed") from None
            except (socket.timeout,TimeoutError):
                if attempt == self.config.retries:
                    raise failure("OpenAI request timed out") from None
            except URLError:
                if attempt == self.config.retries:
                    raise failure("OpenAI transport failed") from None
            except (ValueError, KeyError, TypeError, AttributeError):
                raise failure("Invalid OpenAI response") from None
            self.sleep(min(0.5 * 2 ** attempt, 2))


def model_from_environment():
    provider=os.environ.get("MODEL_PROVIDER","").strip().lower() or (
        "gemini" if os.environ.get("GEMINI_API_KEY", "").strip() and not os.environ.get("OPENAI_API_KEY", "").strip() else "openai")
    if provider not in ("openai","gemini"):
        raise ValueError("Unsupported model provider")
    prefix=provider.upper()
    key = os.environ.get(prefix+"_API_KEY", "").strip()
    if not key:
        return None
    config=ModelConfig(api_key=key,model=os.environ.get(prefix+"_MODEL", "").strip(),
        context_limit=int(os.environ.get(prefix+"_CONTEXT_LIMIT", "0")),
        max_output_tokens=int(os.environ.get(prefix+"_MAX_OUTPUT_TOKENS", "4096")),
        timeout=float(os.environ.get(prefix+"_TIMEOUT_SECONDS", "30")),
        retries=int(os.environ.get(prefix+"_RETRIES", "1")),
        concurrency=int(os.environ.get("CLINICAL_CONCURRENCY", "1")))
    if provider=="gemini":
        from app.gemini_provider import GeminiModel
        return GeminiModel(config)
    return OpenAIModel(config)
