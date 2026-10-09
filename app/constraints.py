"""Source-anchored guideline contracts and three-valued evaluation.

No clinical text parsing or disease/identifier branching lives here.
"""
import hashlib
import json
import math
import operator
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from app.data import SuppliedData
from app.models import ClinicalFact, Contract
from app.trust import scan_untrusted_text

EXTRACTION_VERSION = "manual-draft-v1"
DEFAULT_CACHE = Path(__file__).resolve().parent.parent / "data/derived/guideline_constraints.json"
Outcome = Literal["met", "not_met", "unknown"]


class SourceSpan(Contract):
    source_id: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered_span(self):
        if self.end <= self.start:
            raise ValueError("Source span end must follow start")
        return self


class Condition(Contract):
    fact_key: str = Field(min_length=1)
    fact_kind: Literal["age_years", "sex", "pregnancy_status", "gestational_weeks", "symptom_duration", "test", "finding", "context"]
    operator: Literal["eq", "lt", "le", "gt", "ge", "advisory"]
    expected: Any = None
    unit: Optional[str] = None
    test_name: Optional[str] = None
    description: str = Field(min_length=1)
    source: SourceSpan

    @model_validator(mode="after")
    def machine_syntax(self):
        if self.operator != "advisory":
            if self.fact_kind in ("age_years", "gestational_weeks", "symptom_duration"):
                if type(self.expected) not in (int, float) or not math.isfinite(self.expected):
                    raise ValueError("Numeric conditions require a finite number")
                if self.unit is None:
                    raise ValueError("Numeric conditions require an explicit unit")
            elif self.fact_kind == "test":
                if not self.test_name or self.expected is None:
                    raise ValueError("Test conditions require name and expected result")
                if self.operator != "eq":
                    raise ValueError("Only explicit test-result equality is supported")
            else:
                raise ValueError("Non-age/time/test clinical meaning must stay advisory")
        return self


class ConditionGroup(Contract):
    combine: Literal["all", "any"] = "all"
    conditions: List[Condition] = Field(default_factory=list)


class Relation(Contract):
    kind: Literal["references", "narrows", "supersedes", "overrides"]
    target_source_id: str = Field(min_length=1)
    source: SourceSpan
    rationale: str = Field(min_length=1)
    verification_status: Literal["verified", "uncertain", "rejected"] = "uncertain"


class Review(Contract):
    reviewer: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    note: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GuidelineConstraint(Contract):
    record_id: str = Field(min_length=1)
    source: SourceSpan
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_version: Literal["manual-draft-v1"] = EXTRACTION_VERSION
    extraction_method: Literal["manual_seed", "offline_llm"]
    interpretation: str = Field(min_length=1)
    scope: ConditionGroup = Field(default_factory=ConditionGroup)
    prerequisites: ConditionGroup = Field(default_factory=ConditionGroup)
    time_windows: ConditionGroup = Field(default_factory=ConditionGroup)
    exclusions: ConditionGroup = Field(default_factory=lambda: ConditionGroup(combine="any"))
    relations: List[Relation] = Field(default_factory=list)
    trust_flags: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    coverage: Literal["partial", "reviewed_complete"] = "partial"
    verification_status: Literal["verified", "uncertain", "rejected"] = "uncertain"
    review: Optional[Review] = None

    @model_validator(mode="after")
    def review_required(self):
        if self.verification_status == "verified" and self.review is None:
            raise ValueError("Verified records require an independent human review record")
        if any(r.verification_status == "verified" for r in self.relations) and self.verification_status != "verified":
            raise ValueError("Relations cannot be verified within an unverified record")
        if self.review and self.review.payload_sha256 != payload_sha256(self):
            raise ValueError("Review digest does not match current interpretation")
        return self


class ConstraintCache(Contract):
    schema_version: Literal[1] = 1
    extraction_version: Literal["manual-draft-v1"] = EXTRACTION_VERSION
    guidelines_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: List[GuidelineConstraint]


def payload_sha256(record: GuidelineConstraint) -> str:
    payload = record.model_dump(exclude={"verification_status", "review"})
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def snippet_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_constraint_cache(data: SuppliedData, path: Path = DEFAULT_CACHE) -> ConstraintCache:
    cache = ConstraintCache.model_validate_json(path.read_bytes())
    if cache.guidelines_sha256 != data.guidelines_sha256:
        raise ValueError("Stale constraint cache: guideline-file hash differs")
    sources = {g.id: g for g in data.guidelines}
    if len({r.record_id for r in cache.records}) != len(cache.records):
        raise ValueError("Duplicate constraint record ID")
    if {r.source.source_id for r in cache.records} != set(sources):
        raise ValueError("Cache must account for every supplied guideline")
    for record in cache.records:
        text = sources[record.source.source_id].text
        if record.source_sha256 != snippet_sha256(text):
            raise ValueError(f"Stale snippet hash: {record.record_id}")
        spans = [record.source]
        for group in (record.scope, record.prerequisites, record.time_windows, record.exclusions):
            spans.extend(c.source for c in group.conditions)
        spans.extend(r.source for r in record.relations)
        quarantined = [s for s in scan_untrusted_text(text).segments if s.disposition == "quarantined"]
        for span in spans:
            if span.source_id != record.source.source_id or span.end > len(text) or text[span.start:span.end] != span.source_quote:
                raise ValueError(f"Unanchored source span: {record.record_id}")
        # Whole-source audit quote is permitted to retain malicious text as data;
        # no clinical condition or relation may be grounded in that instruction.
        for span in spans[1:]:
            if any(span.start < s.end and s.start < span.end for s in quarantined):
                raise ValueError(f"Condition/relation overlaps quarantined directive: {record.record_id}")
        for relation in record.relations:
            if relation.target_source_id not in sources:
                raise ValueError(f"Unknown relation target: {relation.target_source_id}")
    return cache


def combine(outcomes: List[Outcome], mode: Literal["all", "any"]) -> Outcome:
    # Empty groups convey absence of extracted knowledge, not satisfaction.
    if not outcomes:
        return "unknown"
    if mode == "all":
        return "not_met" if "not_met" in outcomes else ("unknown" if "unknown" in outcomes else "met")
    return "met" if "met" in outcomes else ("unknown" if "unknown" in outcomes else "not_met")


def _normalize(text):
    return " ".join(text.casefold().split())


def evaluate_condition(condition: Condition, facts: Dict[str, ClinicalFact], original_note: str) -> Outcome:
    """Pure mechanical comparison over grounded facts; never parses clinical prose."""
    if condition.operator == "advisory":
        return "unknown"
    fact = facts.get(condition.fact_key)
    if fact is None or fact.certainty != "known" or fact.kind != condition.fact_kind:
        return "unknown"
    evidence = fact.evidence
    if evidence is None or evidence.source_type != "note" or not _normalize(evidence.source_quote).strip():
        return "unknown"
    note_scan = scan_untrusted_text(original_note)
    if not any(_normalize(evidence.source_quote) in _normalize(segment.text)
               for segment in note_scan.segments if segment.disposition == "retained"):
        return "unknown"
    if evidence.start is not None and (evidence.end > len(original_note) or
                                      original_note[evidence.start:evidence.end] != evidence.source_quote):
        return "unknown"
    if evidence.start is not None and any(segment.disposition == "quarantined" and
            evidence.start < segment.end and segment.start < evidence.end for segment in note_scan.segments):
        return "unknown"
    if any(s.disposition == "quarantined" for s in scan_untrusted_text(evidence.source_quote).segments):
        return "unknown"
    if condition.unit != fact.unit:
        return "unknown"
    value = fact.value
    if condition.fact_kind == "test":
        if fact.test_name != condition.test_name:
            return "unknown"
        value = fact.test_result
        if value is None:
            return "unknown"
    else:
        if type(value) not in (int, float) or not math.isfinite(value):
            return "unknown"
    compare = {"eq": operator.eq, "lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge}
    return "met" if compare[condition.operator](value, condition.expected) else "not_met"


def evaluate_group(group: ConditionGroup, facts: Dict[str, ClinicalFact], original_note: str) -> Outcome:
    return combine([evaluate_condition(c, facts, original_note) for c in group.conditions], group.combine)


def evaluate_record(record: GuidelineConstraint, facts: Dict[str, ClinicalFact], original_note: str) -> Dict[str, Outcome]:
    """Advisory evaluation, never authorization to assign a code.

    Unverified/rejected/partial records cannot supply deterministic hard gates.
    Verified numeric conditions can still be evaluated separately; broader
    clinical applicability and interpretation always require raw-source review.
    """
    names = ("scope", "prerequisites", "time_windows", "exclusions")
    if record.verification_status != "verified" or record.review is None or record.review.payload_sha256 != payload_sha256(record):
        return {name: "unknown" for name in names}
    return {name: evaluate_group(getattr(record, name), facts, original_note) for name in names}


def traverse_relations(cache: ConstraintCache, source_ids: List[str]) -> List[Dict[str, Any]]:
    """Cycle-safe advisory closure. No date-based precedence or authorization."""
    by_source = {}
    for record in cache.records:
        by_source.setdefault(record.source.source_id, []).append(record)
    if any(source_id not in by_source for source_id in source_ids):
        raise ValueError("Unknown starting source")
    queue = list(source_ids)
    visited = set()
    edges = []
    while queue:
        source_id = queue.pop(0)
        if source_id in visited:
            continue
        visited.add(source_id)
        for record in by_source[source_id]:
            if record.verification_status == "rejected":
                continue
            for relation in record.relations:
                if relation.verification_status == "rejected":
                    continue
                edges.append(dict(from_source_id=source_id, record_id=record.record_id,
                                  **relation.model_dump()))
                queue.append(relation.target_source_id)
    return edges
