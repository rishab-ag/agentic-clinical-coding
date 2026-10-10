"""Two-stage orchestration, conservative reconciliation and bounded repair."""
from copy import deepcopy
from pydantic import ValidationError
from concurrent.futures import ThreadPoolExecutor

from app.constraints import evaluate_group
from app.model_contracts import DecisionProposal, ExtractedFindings
from app.model_provider import ContextOverflow, ModelFailure, MalformedOutput, prompt_upper_bound, strict_schema
from app.models import ClinicalFact, Finding
from app.pipeline import NoKeyPipeline, normalize
from app.prompts import PROMPT_VERSION, decision_messages, extraction_messages, messages
from app.trust import scan_untrusted_text


class WireFailure(ValueError):
    def __init__(self, payload, errors):
        super().__init__("Model output schema invalid")
        self.payload = payload
        self.errors = errors


class ReconciliationFailure(ValueError):
    pass


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
        source=offline.guidelines.get(evidence.source_id) or offline.expanded_guidelines.get(evidence.source_id)
        scan=scan_untrusted_text(source.text) if source else None
        if not source or not any(normalize(evidence.source_quote) in normalize(s.text)
            for s in scan.segments if s.disposition=="retained"):
            raise ValueError("Guideline citation/quote not grounded")
        if evidence.start is not None:
            if evidence.end > len(source.text) or normalize(source.text[evidence.start:evidence.end]) != normalize(evidence.source_quote):
                raise ValueError("Guideline quote offsets invalid")
            if not any(s.disposition=="retained" and s.start <= evidence.start < evidence.end <= s.end
                       for s in scan.segments):
                raise ValueError("Guideline span overlaps quarantined text")
    else:
        source=offline.catalogue.get(evidence.source_id)
        if not source or not any(normalize(evidence.source_quote) in normalize(s)
            for s in [source.title,source.chapter]+source.synonyms):
            raise ValueError("Catalogue citation/quote not grounded")
        if evidence.start is not None:
            raise ValueError("Catalogue spans require an unambiguous source field; use quotes")
    if not normalize(evidence.source_quote):
        raise ValueError("Blank source quote")


class ModelPipeline:
    def __init__(self,data,model,expansion_path=None):
        self.offline=NoKeyPipeline(data,expansion_path=expansion_path)
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
        record=deepcopy(record)
        baseline=self.offline.process(record)
        if record.errors:
            return baseline
        result=baseline.model_copy(deep=True)
        provenance=result.provenance
        provenance.mode="model"
        provenance.provider=getattr(self.model,"provider","openai")
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
            original_messages=decision_messages(record.note,extraction,result,self.offline)
            proposal=None
            try:
                proposal=self._stage("decide",original_messages,DecisionProposal,provenance)
                self._validate(proposal,extraction,record.note,result.facts)
            except (WireFailure, ReconciliationFailure) as error:
                if not hasattr(self.model,"repair"):
                    raise
                original=deepcopy(error.payload if isinstance(error,WireFailure) else proposal.model_dump())
                # Unparseable certainty cannot be upgraded by repair. The repair
                # may only retain identical assignments from the first proposal.
                repair_messages=original_messages + messages(
                    "Repair output structure/accounting once. Do not add or change assignments, "
                    "existing guideline assessments, evidence, assertions or clinical certainty. "
                    "Assessments may be added only for guideline IDs missing from the output. "
                    "Remove invalid assignments or refuse. Original sources remain authoritative.",
                    dict(invalid_output=original,validator_errors=(error.errors if isinstance(error,WireFailure) else str(error))))
                provenance.model_repairs+=1
                repaired=self._stage("repair",repair_messages,DecisionProposal,provenance)
                self._repair_guard(original,repaired)
                self._validate(repaired,extraction,record.note,result.facts)
                proposal=repaired
                result.warnings.append("One structural repair revalidated against original sources")
            dispositions={d.finding_id:d for d in proposal.dispositions}
            for finding in result.findings:
                disposition=dispositions[finding.finding_id]
                finding.disposition=disposition.disposition
                finding.reason=disposition.reason
                finding.assignment_code=disposition.assignment_code
            result.assignments=proposal.assignments
            result.status="unresolved" if not result.assignments else (
                "provisional" if any(a.certainty=="provisional" for a in result.assignments) else "coded")
            result.candidates_considered=list({(c.catalogue_origin,c.code):c for c in
                result.candidates_considered+proposal.candidates_considered}.values())
            result.warnings.extend(f"Expanded-only candidate {c.code}: outside supplied catalogue; source {c.source}"
                                   for c in result.candidates_considered if c.catalogue_origin=="expanded")
            result.safety_flags=list(dict.fromkeys(result.safety_flags+proposal.safety_flags))
            result.warnings=list(dict.fromkeys(result.warnings+proposal.warnings+
                [f"{g.id}: {w}" for g in self.offline.data.guidelines for w in self.offline.guideline_scans[g.id].warnings]))
            result.unresolved=proposal.unresolved
            result.confidence=proposal.confidence
            from app.models import CodingResult
            return CodingResult.model_validate(result.model_dump())
        except Exception as error:
            if 'proposal' in locals() and proposal is not None:
                result.safety_flags=list(dict.fromkeys(result.safety_flags+proposal.safety_flags))
                result.warnings=list(dict.fromkeys(result.warnings+proposal.warnings))
                for candidate in proposal.candidates_considered:
                    if candidate.catalogue_origin=="expanded":
                        candidate=candidate.model_copy(deep=True)
                        candidate.status="unresolved"
                        entry=self.offline.expanded_catalogue.get(candidate.code)
                        if entry:
                            candidate.title=entry.title
                            candidate.source=entry.source.url
                            candidate.reason="Source-reviewed external candidate; clinical assignment validation failed"
                        else:
                            candidate.reason="Unverified model-proposed expanded candidate; not eligible for assignment"
                        result.candidates_considered=[c for c in result.candidates_considered
                            if (c.catalogue_origin,c.code)!=("expanded",candidate.code)]+[candidate]
                        result.warnings.append("Expanded-only candidate retained unresolved; source reviewed" if entry else
                                               "Expanded candidate provenance unverified; source is a model claim, not verification")
            result.assignments=[]
            result.status="unresolved"
            result.confidence=baseline.confidence
            for finding in result.findings:
                finding.disposition="unresolved"
                finding.assignment_code=None
                finding.reason="Model reasoning failed validation; retained for review"
            result.unresolved=baseline.unresolved+[f"Model path refused ({type(error).__name__}); no assignment accepted"]
            if 'proposal' in locals() and proposal is not None:
                result.unresolved.extend(proposal.unresolved)
            result.warnings.append("Validation failed; source uncertainty retained")
            if isinstance(error,ModelFailure):
                result.unresolved.append(str(error))
            if isinstance(error,WireFailure):
                for issue in error.errors:
                    location=".".join(str(part) for part in issue.get("location",[])) or "<root>"
                    result.unresolved.append(f"Schema validation: {location}: {issue['type']}")
                    if issue.get("value_type"):
                        result.unresolved.append(f"Schema fact value representation: {issue['value_type']}")
            if isinstance(error,(ValueError,WireFailure)) and not isinstance(error,ValidationError):
                result.unresolved.append(str(error))
            return result

    def _repair_guard(self,original,repaired):
        if not isinstance(original,dict):
            if repaired.assignments:
                raise ValueError("Unparseable output cannot authorize repaired assignments")
            return
        allowed=original.get("assignments",[])
        for assignment in repaired.assignments:
            # Compare through the contract to account for nullable defaults only.
            from app.models import Assignment
            permitted=[]
            for item in allowed if isinstance(allowed,list) else []:
                try: permitted.append(Assignment.model_validate(item).model_dump())
                except (ValidationError,TypeError): pass
            if assignment.model_dump() not in permitted:
                raise ValueError("Repair added or changed assignment/evidence/certainty")
        if repaired.assignments:
            before={g.source_id:g for g in DecisionProposal.model_validate(
                dict(original,dispositions=repaired.model_dump()["dispositions"])).guideline_review}
            # Omitted reviews may be added; an existing assessment is immutable.
            if {g.source_id:g for g in repaired.guideline_review if g.source_id in before}!=before:
                raise ValueError("Repair changed guideline applicability")
        levels={"low":0,"moderate":1,"high":2}
        before=original.get("confidence",{}).get("level","low")
        if levels[repaired.confidence.level]>levels.get(before,0):
            raise ValueError("Repair increased confidence")

    def _stage(self,name,messages,contract,provenance):
        schema=strict_schema(contract)
        label="clinical_extraction" if name=="extract" else "clinical_decision"
        bound=(self.model.prompt_bound(messages,schema,label) if hasattr(self.model,"prompt_bound") else
               prompt_upper_bound(self.model.config,messages,schema,label))
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
            if isinstance(error,MalformedOutput):
                raise WireFailure(error.payload,[dict(type="invalid_json")]) from None
            raise
        provenance.stage_prompt_tokens[name]=reply.input_tokens
        provenance.prompt_token_count=sum(provenance.stage_prompt_tokens.values())
        provenance.prompt_token_count_method="api_usage"
        provenance.model_retries+=reply.retries
        provenance.model_latency_ms+=reply.latency_ms
        if reply.input_tokens+self.model.config.max_output_tokens > self.model.config.context_limit:
            raise ContextOverflow("Actual API token usage exceeds configured reserve")
        try:
            return contract.model_validate(reply.payload)
        except ValidationError as error:
            # Exclude arbitrary untrusted inputs from error summaries.
            raise WireFailure(deepcopy(reply.payload),[
                dict(location=(list(e["loc"][:-1])+["<unexpected field>"] if e["type"]=="extra_forbidden" else list(e["loc"])),
                     type=e["type"],value_type=(type(e["input"].get("value")).__name__
                        if e["type"]=="value_error" and isinstance(e.get("input"),dict) and "value" in e["input"] else None))
                for e in error.errors()]) from None

    def _validate(self,proposal,extraction,note,facts):
        findings={f.finding_id:f for f in extraction.findings}
        if len(proposal.dispositions)!=len(findings) or {d.finding_id for d in proposal.dispositions}!=set(findings):
            raise ReconciliationFailure("Every finding requires exactly one disposition")
        assignments={a.code:a for a in proposal.assignments}
        if len(assignments)!=len(proposal.assignments):
            raise ValueError("Duplicate assignment code")
        for disposition in proposal.dispositions:
            if not disposition.reason.strip():
                raise ReconciliationFailure("Every disposition requires a nonblank reason")
            if disposition.disposition in ("coded","subsumed"):
                if disposition.assignment_code not in assignments:
                    raise ValueError("Coded/subsumed disposition lacks assignment")
                if disposition.finding_id not in assignments[disposition.assignment_code].finding_ids:
                    raise ReconciliationFailure("Coded/subsumed finding is not assignment-linked; correct dispositions without changing assignments")
            elif disposition.assignment_code is not None:
                raise ValueError("Non-coded disposition cannot claim assignment")
        reviews={g.source_id:g for g in proposal.guideline_review}
        required=set(self.offline.guidelines)|set(self.offline.expanded_guidelines)
        if len(reviews)!=len(proposal.guideline_review) or set(reviews)-required:
            raise ValueError("Guideline review has duplicate or unknown IDs")
        missing=required-set(reviews)
        if missing and proposal.assignments:
            raise ReconciliationFailure("Guideline review omits loaded guideline IDs; add only the missing assessments "
                                        "without changing assignments or existing assessments")
        if missing:
            # A refusal needs no authorization; the gap stays unknown, never inapplicable.
            warning=f"Model omitted {len(missing)} guideline reviews; treated as unknown, not as inapplicable"
            if warning not in proposal.warnings: proposal.warnings.append(warning)
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
            if candidate.catalogue_origin=="expanded":
                entry=self.offline.expanded_catalogue.get(candidate.code)
                if not entry or candidate.title!=entry.title or candidate.status!="unresolved":
                    raise ValueError("Expanded candidate lacks independent source review or unresolved status")
                candidate.source=entry.source.url
                candidate.reason="Source-reviewed external candidate; outside supplied assignment catalogue"
                continue
            entry=self.offline.catalogue.get(candidate.code)
            if candidate.catalogue_origin!="supplied" or not entry or candidate.title!=entry.title:
                raise ValueError("Candidate outside loaded supplied catalogue")
            candidate.source="data/icd_catalog.json"
        for assignment in proposal.assignments:
            if len(set(assignment.finding_ids))!=len(assignment.finding_ids):
                raise ValueError("Duplicate linked finding")
            if any(d.disposition not in ("coded","subsumed") or d.assignment_code!=assignment.code
                   for d in proposal.dispositions if d.finding_id in assignment.finding_ids):
                raise ValueError("Assignment contradicts linked finding disposition")
            if (proposal.unresolved or proposal.safety_flags or any(d.disposition=="unresolved" for d in proposal.dispositions)) and (
                proposal.confidence.level=="high" or assignment.confidence.level=="high"):
                raise ValueError("Unresolved finding or safety concern blocks high confidence")
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
            if not any(e.source_type=="note" and normalize(e.source_quote)==normalize(findings[i].evidence.source_quote)
                       for e in assignment.evidence for i in assignment.finding_ids):
                raise ValueError("Assignment note evidence does not match a linked finding")
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
                        # Advisory clinical interpretations are not hard gates.
                        numeric=group.model_copy(update={"conditions":[c for c in group.conditions if c.operator!="advisory"]})
                        if group.combine=="any" and len(numeric.conditions)!=len(group.conditions):
                            continue
                        if numeric.conditions and evaluate_group(numeric,grounded,note.text)!="met":
                            raise ValueError("Verified numeric/test gate not met")
                    if constraint.exclusions.conditions and all(c.operator!="advisory" for c in constraint.exclusions.conditions) and evaluate_group(constraint.exclusions,grounded,note.text)!="not_met":
                        raise ValueError("Verified exclusion not safely ruled out")
                    for relation in constraint.relations:
                        if relation.verification_status=="verified" and reviews[relation.target_source_id].applicability=="unknown":
                            raise ValueError("Verified cross-guideline dependency unresolved")
