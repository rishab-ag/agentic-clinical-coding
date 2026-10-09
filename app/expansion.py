"""Separate external source proposals; only digest-bound human reviews activate data.

This validates recorded review metadata, not the identity of the reviewer or
clinical correctness. No network access or automatic approval occurs here.
"""
import hashlib
import json
from pathlib import Path
from typing import List, Literal, Optional
from urllib.parse import urlparse
from pydantic import Field, model_validator
from app.models import Contract
from app.ingestion import _json

DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / 'data/expanded/proposals.json'

class SourceRecord(Contract):
    url: str
    publisher: str = Field(min_length=1)
    accessed_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    version: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    fragment: str = Field(min_length=1)
    fragment_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    license_url: Optional[str] = None
    attribution_note: str = Field(min_length=1)
    fetched_facts: List[str] = Field(min_length=1)
    unverified_facts: List[str]

    @model_validator(mode='after')
    def integrity(self):
        for url in [self.url] + ([self.license_url] if self.license_url else []):
            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Source URLs must be HTTPS without credentials')
        if hashlib.sha256(self.fragment.encode()).hexdigest()!=self.fragment_sha256:
            raise ValueError('Source fragment hash mismatch')
        return self

class ExternalReview(Contract):
    reviewer: str = Field(min_length=1, pattern=r'\S')
    reviewed_at: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    exact_mapping_checked: bool
    source_checked: bool
    reuse_permission_checked: bool
    note: str = Field(min_length=1)

class ExternalEntry(Contract):
    entry_id: str = Field(min_length=1)
    kind: Literal['catalogue','guideline']
    catalogue_origin: Literal['expanded'] = 'expanded'
    code: Optional[str] = None
    title: str = Field(min_length=1)
    chapter: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    text: Optional[str] = None
    icd_uri: Optional[str] = None
    source: SourceRecord
    reason: str = Field(min_length=1)
    linked_supplied_guideline_ids: List[str]
    review_status: Literal['pending_human_review','human_approved','rejected'] = 'pending_human_review'
    review: Optional[ExternalReview] = None

    @model_validator(mode='after')
    def approval(self):
        if self.kind=='catalogue' and (not self.code or self.text is not None):
            raise ValueError('Catalogue proposal needs code and no guideline text')
        if self.kind=='catalogue' and (self.code not in self.source.fragment or self.title not in self.source.fragment):
            raise ValueError('Code/title must occur in the stored fetched source fragment')
        if self.kind=='guideline' and (self.code is not None or not self.text or self.text not in self.source.fragment):
            raise ValueError('Guideline excerpt must be grounded in stored source fragment')
        if self.review_status=='human_approved':
            r=self.review
            if not r or not (r.source_checked and r.exact_mapping_checked and r.reuse_permission_checked):
                raise ValueError('Independent source/mapping/reuse review required')
            if r.payload_sha256!=entry_digest(self):
                raise ValueError('Approval digest stale')
            if self.kind=='catalogue' and (not self.icd_uri or not self.chapter):
                raise ValueError('Approved ICD entry needs WHO entity URI and chapter')
            if self.icd_uri and not self.icd_uri.startswith('http://id.who.int/icd/entity/'):
                raise ValueError('Expected WHO foundation entity URI')
        return self

def entry_digest(entry):
    payload=entry.model_dump(exclude={'review','review_status'})
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

class ExpansionManifest(Contract):
    schema_version: Literal['external-proposals-v1']
    entries: List[ExternalEntry]

    @model_validator(mode='after')
    def unique(self):
        for keys in ([e.entry_id for e in self.entries], [e.code for e in self.entries if e.kind=='catalogue']):
            if len(keys)!=len(set(keys)): raise ValueError('Duplicate external identifier')
        return self

def load_expansion(data, path=DEFAULT_MANIFEST):
    manifest=ExpansionManifest.model_validate(_json(Path(path).read_text(encoding='utf-8')))
    supplied_codes={e.code for e in data.catalogue}
    supplied_ids={g.id for g in data.guidelines}
    for entry in manifest.entries:
        if entry.entry_id in supplied_ids or entry.code in supplied_codes:
            raise ValueError('External identifier collides with supplied corpus; never overwrite')
        if not set(entry.linked_supplied_guideline_ids)<=supplied_ids:
            raise ValueError('Unknown supplied guideline linkage')
    return manifest, hashlib.sha256(Path(path).read_bytes()).hexdigest()
