"""Two-stage orchestration and necessary local grounding checks.

No repair loop or full Milestone 6 reconciliation engine is implemented here.
"""
from concurrent.futures import ThreadPoolExecutor

from app.constraints import evaluate_condition
from app.model_contracts import DecisionProposal, ExtractedFindings
from app.model_provider import ContextOverflow, ModelFailure, prompt_upper_bound, strict_schema
from app.models import ClinicalFact, Finding
from app.pipeline import NoKeyPipeline, normalize
from app.prompts import PROMPT_VERSION, decision_messages, extraction_messages
from app.trust import scan_untrusted_text


def note_evidence(evidence, note):
    if evidence.source_type != "note" or evidence.source_id != note.note_id or not normalize(evidence.source_quote):
        raise ValueError("Evidence is not original-note evidence")
    retained = [s for s in scan_untrusted_text(note.text).segments if s.disposition=="retained"]
    if not any(normalize(evidence.source_quote) in normalize(s.text) for s in retained):
        raise ValueError("Quote missing from retained original note")
    if evidence.start is not None:
        if evidence.end > len(note.text) or normalize(note.text[evidence.start:evidence.end]) != normalize(evidence.source_quote):
            raise ValueError("Quote offsets invalid")
        if not any(s.start <= evidence.start < evidence.end <= s.end for s in retained):
            raise ValueError("Quote overlaps quarantined instructions")


def source_evidence(evidence, offline, note):
    if evidence.source_type=="note":
        return note_evidence(evidence,note)
    if evidence.source_type=="guideline":
        source=offline.guidelines.get(evidence.source_id)
        if not source or not any(normalize(evidence.source_quote) in normalize(s.text)
            for s in offline.guideline_scans[source.id].segments if s.disposition=="retained"):
            raise ValueError("Guideline citation/quote not grounded")
    else:
        source=offline.catalogue.get(evidence.source_id)
        if not source or not any(normalize(evidence.source_quote) in normalize(s)
            for s in [source.title,source.chapter]+source.synonyms):
            raise ValueError("Catalogue citation/quote not grounded")
    if not normalize(evidence.source_quote):
        raise ValueError("Blank source quote")


class ModelPipeline:
    def __init__(self,data,model):
        self.offline=NoKeyPipeline(data)
        self.model=model

    def run(self,records):
        def safe(record):
            try:
                return self.process(record)
            except Exception:
                result=next(self.offline.run([record]))
                result.warnings.append("Model orchestration failed; conservative offline result retained")
                return result
        if self.model.config.concurrency==1:
            for record in records: yield safe(record)
        else:
            with ThreadPoolExecutor(max_workers=self.model.config.concurrency) as executor:
                yield from executor.map(safe,records)

    def process(self,record):
        baseline=self.offline.process(record)
        if record.errors:
            return baseline
        result=baseline.model_copy(deep=True)
        provenance=result.provenance
        provenance.mode="model"
        provenance.provider="openai"
        provenance.model=self.model.config.model
        provenance.prompt_version=PROMPT_VERSION
        try:
            extraction=self._stage("extract",extraction_messages(record.note),ExtractedFindings,provenance)
            ids=[f.finding_id for f in extraction.findings]
            if len(set(ids))!=len(ids) or any(not identifier for identifier in ids):
                raise ValueError("Stage 1 finding IDs invalid")
            if not ids and any(s.disposition=="retained" and s.text.strip() for s in scan_untrusted_text(record.note.text).segments):
                raise ValueError("Nonempty retained note needs a finding or explicit unresolved segment")
            for finding in extraction.findings:
                note_evidence(finding.evidence,record.note)
            for fact in extraction.facts:
                note_evidence(fact.evidence,record.note)
            result.findings=[Finding(**f.model_dump(),disposition="unresolved",
                reason="Model extraction retained; no validated assignment yet") for f in extraction.findings]
            result.facts=[ClinicalFact(**f.model_dump(),extraction_method="model") for f in extraction.facts]
            result.differential_hypotheses=extraction.differential_hypotheses
            # Stage 1 hypotheses aid recall only; they never become findings/evidence.
            terms=" ".join(h.text for h in extraction.differential_hypotheses)
            if terms:
                hits=self.offline.catalogue_index.search(scan_untrusted_text(terms).retained_text)
                from app.models import Candidate
                for code,score in hits:
                    if code not in {c.code for c in result.candidates_considered}:
                        entry=self.offline.catalogue[code]
                        result.candidates_considered.append(Candidate(code=code,title=entry.title,catalogue_origin="supplied",
                            retrieval_score=score,source="data/icd_catalog.json",status="unresolved",
                            reason="Non-evidentiary differential retrieval only",missing_discriminators=["Original-note confirmation"]))
            corpus_warnings=[f"{g.id}: {w}" for g in self.offline.data.guidelines for w in self.offline.guideline_scans[g.id].warnings]
            result.warnings.extend(corpus_warnings)
            if corpus_warnings and "quarantine_injected_guideline_directive" not in result.safety_flags:
                result.safety_flags.append("quarantine_injected_guideline_directive")
            proposal=self._stage("decide",decision_messages(record.note,extraction,result,self.offline),DecisionProposal,provenance)
            self._validate(proposal,extraction,record.note,result.facts)
            dispositions={d.finding_id:d for d in proposal.dispositions}
            for finding in result.findings:
                disposition=dispositions[finding.finding_id]
                finding.disposition=disposition.disposition
                finding.reason=disposition.reason
                finding.assignment_code=disposition.assignment_code
            result.assignments=proposal.assignments
            result.status="unresolved" if not result.assignments else (
                "provisional" if any(a.certainty=="provisional" for a in result.assignments) else "coded")
            result.candidates_considered=proposal.candidates_considered
            result.safety_flags=list(dict.fromkeys(result.safety_flags+proposal.safety_flags))
            result.warnings=list(dict.fromkeys(result.warnings+proposal.warnings+
                [f"{g.id}: {w}" for g in self.offline.data.guidelines for w in self.offline.guideline_scans[g.id].warnings]))
            result.unresolved=proposal.unresolved
            result.confidence=proposal.confidence
            from app.models import CodingResult
            return CodingResult.model_validate(result.model_dump())
        except Exception as error:
            result.assignments=[]
            result.status="unresolved"
            result.confidence=baseline.confidence
            for finding in result.findings:
                finding.disposition="unresolved"
                finding.assignment_code=None
                finding.reason="Model reasoning failed validation; retained for review"
            result.unresolved=baseline.unresolved+[f"Model path refused ({type(error).__name__}); no assignment accepted"]
            result.warnings.append("No formatting/clinical repair attempted; source uncertainty retained")
            return result

    def _stage(self,name,messages,contract,provenance):
        schema=strict_schema(contract)
        bound=prompt_upper_bound(self.model.config,messages,schema,
                                 "clinical_extraction" if name=="extract" else "clinical_decision")
        provenance.stage_prompt_upper_bounds[name]=bound
        if not provenance.stage_prompt_tokens:
            provenance.prompt_token_count=bound
            provenance.prompt_token_count_method="utf8_upper_bound"
        if bound+self.model.config.max_output_tokens > self.model.config.context_limit:
            raise ContextOverflow("Untruncated context exceeds configured limit")
        try:
            reply=getattr(self.model,name)(messages,schema)
        except ModelFailure as error:
            provenance.model_retries+=error.retries
            provenance.model_latency_ms+=error.latency_ms
            if error.input_tokens is not None:
                provenance.stage_prompt_tokens[name]=error.input_tokens
                provenance.prompt_token_count=sum(provenance.stage_prompt_tokens.values())
                provenance.prompt_token_count_method="api_usage"
            raise
        provenance.stage_prompt_tokens[name]=reply.input_tokens
        provenance.prompt_token_count=sum(provenance.stage_prompt_tokens.values())
        provenance.prompt_token_count_method="api_usage"
        provenance.model_retries+=reply.retries
        provenance.model_latency_ms+=reply.latency_ms
        if reply.input_tokens+self.model.config.max_output_tokens > self.model.config.context_limit:
            raise ContextOverflow("Actual API token usage exceeds configured reserve")
        return contract.model_validate(reply.payload)

    def _validate(self,proposal,extraction,note,facts):
        findings={f.finding_id:f for f in extraction.findings}
        if len(proposal.dispositions)!=len(findings) or {d.finding_id for d in proposal.dispositions}!=set(findings):
            raise ValueError("Every finding requires exactly one disposition")
        assignments={a.code:a for a in proposal.assignments}
        if len(assignments)!=len(proposal.assignments):
            raise ValueError("Duplicate assignment code")
        for disposition in proposal.dispositions:
            if disposition.disposition in ("coded","subsumed"):
                if disposition.assignment_code not in assignments:
                    raise ValueError("Coded/subsumed disposition lacks assignment")
                if disposition.disposition=="coded" and disposition.finding_id not in assignments[disposition.assignment_code].finding_ids:
                    raise ValueError("Coded finding is not assignment-linked")
            elif disposition.assignment_code is not None:
                raise ValueError("Non-coded disposition cannot claim assignment")
        reviews={g.source_id:g for g in proposal.guideline_review}
        if len(reviews)!=len(proposal.guideline_review) or set(reviews)!=set(self.offline.guidelines):
            raise ValueError("All supplied guidelines require review")
        for review in reviews.values():
            for requirement in review.requirements:
                if requirement.source.source_type!="guideline" or requirement.source.source_id!=review.source_id:
                    raise ValueError("Requirement source mismatch")
                source_evidence(requirement.source,self.offline,note)
                for evidence in requirement.evidence:
                    note_evidence(evidence,note)
                if requirement.outcome=="met" and not requirement.evidence:
                    raise ValueError("Met requirements need original-note evidence")
        for candidate in proposal.candidates_considered:
            entry=self.offline.catalogue.get(candidate.code)
            if candidate.catalogue_origin!="supplied" or not entry or candidate.title!=entry.title:
                raise ValueError("Candidate outside loaded supplied catalogue")
            candidate.source="data/icd_catalog.json"
        for assignment in proposal.assignments:
            if assignment.code not in self.offline.catalogue or not assignment.guideline_ids:
                raise ValueError("Assignment/code citations missing")
            if any(identifier not in findings for identifier in assignment.finding_ids):
                raise ValueError("Assignment links non-finding evidence")
            if any(g.applicability=="unknown" for g in reviews.values()):
                raise ValueError("Unknown guideline applicability blocks assignment")
            for evidence in assignment.evidence:
                source_evidence(evidence,self.offline,note)
            if not any(e.source_type=="note" for e in assignment.evidence):
                raise ValueError("Assignment lacks original-note evidence")
            if assignment.certainty=="definitive":
                if not any(findings[i].assertion=="confirmed" and findings[i].encounter_relevant is True and
                    findings[i].temporality=="current" and findings[i].experiencer=="patient" for i in assignment.finding_ids):
                    raise ValueError("Definitive assignment lacks confirmed current encounter finding")
                if any(g.applicability=="unknown" for g in reviews.values()):
                    raise ValueError("Unknown guideline applicability blocks definitive assignment")
            else:
                permission=assignment.provisional_permission
                if permission is None or permission.source_type!="guideline" or permission.source_id not in assignment.guideline_ids:
                    raise ValueError("Provisional assignment requires grounded applicable permission")
                source_evidence(permission,self.offline,note)
            for source_id in assignment.guideline_ids:
                if source_id not in reviews or reviews[source_id].applicability!="met":
                    raise ValueError("Assignment cites non-applicable guidance")
            for review in reviews.values():
                if review.applicability=="met" and any(r.applies_to in ("all",assignment.certainty) and r.outcome!="met" for r in review.requirements):
                    raise ValueError("Required evidence not met")
            if self.offline.cache:
                grouped={}
                for fact in facts: grouped.setdefault(fact.kind,[]).append(fact)
                grounded={key:values[0] for key,values in grouped.items() if len(values)==1}
                for constraint in self.offline.cache.records:
                    if constraint.verification_status!="verified" or reviews[constraint.source.source_id].applicability!="met": continue
                    for group in (constraint.scope,constraint.prerequisites,constraint.time_windows):
                        for condition in group.conditions:
                            if condition.operator!="advisory" and evaluate_condition(condition,grounded,note.text)!="met":
                                raise ValueError("Verified numeric/test gate not met")
