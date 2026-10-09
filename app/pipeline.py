"""Conservative offline pipeline. No model calls or clinical keyword rules.

No assignment route is enabled without independent applicability review. A
retrieval miss or an unverified prerequisite cannot establish authorization.
"""
import hashlib
import math
import re
from pathlib import Path

from app.constraints import DEFAULT_CACHE, evaluate_record, load_constraint_cache
from app.ingestion import InputRecord
from app.models import (Candidate, ClinicalFact, CodingResult, Confidence, Evidence,
                        Finding, GuidelineCheck, Provenance, RetrievedContext)
from app.retrieval import BM25, SearchDocument
from app.trust import scan_untrusted_text


def normalize(text):
    return " ".join(text.casefold().split())


class NoKeyPipeline:
    def __init__(self, data, cache_path: Path = DEFAULT_CACHE):
        self.data = data
        self.catalogue = {entry.code: entry for entry in data.catalogue}
        self.guidelines = {entry.id: entry for entry in data.guidelines}
        self.titles = {}
        for entry in data.catalogue:
            self.titles.setdefault(normalize(entry.title), []).append(entry)
        self.catalogue_index = BM25([SearchDocument(source_id=e.code,
            text=scan_untrusted_text(" ".join([e.title, e.chapter] + e.synonyms)).retained_text) for e in data.catalogue])
        self.guideline_scans = {g.id: scan_untrusted_text(g.text) for g in data.guidelines}
        self.guideline_index = BM25([SearchDocument(source_id=g.id,
            text=scan_untrusted_text(g.title).retained_text + " " + self.guideline_scans[g.id].retained_text) for g in data.guidelines])
        self.cache, self.cache_warning, self.cache_hash = None, None, None
        try:
            self.cache = load_constraint_cache(data, cache_path)
            self.cache_hash = hashlib.sha256(cache_path.read_bytes()).hexdigest()
        except (OSError, ValueError):
            self.cache_warning = "Constraint cache missing, invalid or stale; using raw guidance and refusing assignments"

    def provenance(self):
        return Provenance(mode="deterministic", catalogue_sha256=self.data.catalogue_sha256,
                          guidelines_sha256=self.data.guidelines_sha256, constraints_sha256=self.cache_hash)

    def extract(self, record):
        scan = scan_untrusted_text(record.note.text)
        findings, facts, quarantined, exact_titles = [], [], [], []
        for segment in scan.segments:
            if segment.disposition == "quarantined":
                quarantined.append(Evidence(source_type="note",source_id=record.note.note_id,
                    source_quote=segment.text,start=segment.start,end=segment.end))
                continue
            cursor = segment.start
            for line in segment.text.splitlines(keepends=True):
                start, end = cursor, cursor + len(line)
                cursor = end
                if not line.strip():
                    continue
                quote = Evidence(source_type="note",source_id=record.note.note_id,
                                 source_quote=line,start=start,end=end)
                assertion, finding_type, relevant = "unclear", "other", None
                if line.casefold().startswith("clinician diagnosis:"):
                    diagnosis = line.split(":", 1)[1].strip()
                    entries = self.titles.get(normalize(diagnosis), [])
                    if len(entries) == 1:
                        # Explicit current-diagnosis field only; still no authorization.
                        assertion, finding_type, relevant = "confirmed", "diagnosis", True
                        exact_titles.append(entries[0].title)
                attributes = {}
                match = re.fullmatch(r"Age:\s*(\d+(?:\.\d+)?)\s+years\s*", line, flags=re.I)
                if match and math.isfinite(float(match.group(1))):
                    value = float(match.group(1))
                    fact = ClinicalFact(kind="age_years",value=value,unit="years",evidence=quote,
                        extraction_method="explicit_numeric",certainty="known")
                    facts.append(fact)
                    attributes["age_years"] = fact
                match = re.fullmatch(r"Duration:\s*(\d+(?:\.\d+)?)\s+(minutes|hours|days|weeks|months|years)\s*", line, flags=re.I)
                if match and math.isfinite(float(match.group(1))):
                    fact = ClinicalFact(kind="symptom_duration",value=float(match.group(1)),unit=match.group(2).casefold(),
                        evidence=quote,extraction_method="explicit_numeric",certainty="known")
                    facts.append(fact)
                    attributes["symptom_duration"] = fact
                findings.append(Finding(finding_id=f"f{len(findings)+1}",type=finding_type,evidence=quote,
                    assertion=assertion,encounter_relevant=relevant,attributes=attributes,disposition="unresolved",
                    reason="Retained input segment; clinical interpretation/applicability not established by this narrow offline path"))
        return findings, facts, quarantined, exact_titles, scan

    def process(self, record: InputRecord) -> CodingResult:
        findings, facts, quarantined, exact_titles, scan = self.extract(record)
        result = CodingResult(note_id=record.note.note_id,original_note=record.note.text,
            original_record=record.original_record,input_position=record.position,status="unresolved",
            findings=findings,facts=facts,quarantined_note_evidence=quarantined,
            warnings=record.warnings + scan.warnings + ([self.cache_warning] if self.cache_warning else []),
            safety_flags=(["quarantine_injected_note_directive"] if quarantined else []),
            unresolved=record.errors + ["Independent guideline applicability review is unavailable; no safe assignment authorization"],
            confidence=Confidence(level="low",increase_if=["Independent review establishes applicable guidance and all required evidence"],
                                  decrease_if=["Contradictory findings, missing prerequisites, untrusted source instructions"]),
            provenance=self.provenance())
        if record.errors:
            return result
        try:
            safe_note = scan.retained_text
            catalogue_hits = self.catalogue_index.search(safe_note, limit=5)
            query = safe_note + " " + " ".join(exact_titles or [self.catalogue[code].title for code, _ in catalogue_hits])
            guideline_hits = self.guideline_index.search(query, limit=7)
            for code, score in catalogue_hits:
                entry = self.catalogue[code]
                result.candidates_considered.append(Candidate(code=code,title=entry.title,catalogue_origin="supplied",
                    retrieval_score=score,source="data/icd_catalog.json",status="unresolved",
                    reason="Lexical candidate only; retrieval score is not clinical confidence",
                    missing_discriminators=["Independent guideline applicability review", "Sufficient confirmed encounter evidence and met prerequisites"]))
                result.retrieved_evidence.append(RetrievedContext(source_type="catalogue",source_id=code,title=entry.title,
                    retrieval_score=score,source_quote=entry.title,raw_text=" | ".join([entry.code,entry.title,entry.chapter]+entry.synonyms),
                    source_sha256=self.data.catalogue_sha256))
            hit_ids = set()
            for identifier, score in guideline_hits:
                hit_ids.add(identifier)
                source = self.guidelines[identifier]
                source_scan = self.guideline_scans[identifier]
                excerpt = next((s.text.strip()[:500] for s in source_scan.segments if s.disposition == "retained" and s.text.strip()), "")
                result.retrieved_evidence.append(RetrievedContext(source_type="guideline",source_id=identifier,title=source.title,
                    retrieval_score=score,source_quote=excerpt,raw_text=source.text,
                    source_sha256=hashlib.sha256(source.text.encode("utf-8")).hexdigest(),warnings=source_scan.warnings))
                result.warnings.extend(source_scan.warnings)
                if source_scan.warnings and "quarantine_injected_guideline_directive" not in result.safety_flags:
                    result.safety_flags.append("quarantine_injected_guideline_directive")
            if self.cache:
                # Facts are never guessed from shorthand or unstructured test text.
                ages = [fact for fact in facts if fact.kind == "age_years"]
                grounded = {"age_years": ages[0]} if len(ages) == 1 else {}
                for constraint in self.cache.records:
                    if constraint.source.source_id in hit_ids:
                        result.guideline_checks.append(GuidelineCheck(source_id=constraint.source.source_id,
                            record_id=constraint.record_id,verification_status=constraint.verification_status,
                            outcomes=evaluate_record(constraint,grounded,record.note.text)))
            result.warnings += ["Retrieval misses do not establish absence of applicable guidance",
                               "Offline extraction retains source segments; it does not claim full clinical finding recall"]
            if not catalogue_hits:
                result.unresolved.append("No positive lexical catalogue match; refusing nearest-code substitution")
        except Exception as error:
            # Keep already extracted findings and any retrieved context; no note text in logs.
            result.unresolved.append(f"Per-record processing failed ({type(error).__name__}); retained input and findings")
        return CodingResult.model_validate(result.model_dump())

    def run(self, records):
        for record in records:
            try:
                yield self.process(record)
            except Exception as error:
                yield CodingResult(note_id=record.note.note_id,original_note=record.note.text,
                    original_record=record.original_record,input_position=record.position,status="unresolved",
                    unresolved=record.errors + [f"Per-record failure ({type(error).__name__}); input retained"],
                    warnings=record.warnings,confidence=Confidence(level="low"),provenance=self.provenance())
