"""Structural contracts only; clinical/source validation belongs to later milestones."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Note(Contract):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    note_id: str = Field(min_length=1)
    text: str


class Evidence(Contract):
    source_type: Literal["note", "catalogue", "guideline"]
    source_id: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    start: Optional[int] = Field(default=None, ge=0)
    end: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid_offsets(self):
        if (self.start is None) != (self.end is None):
            raise ValueError("Offsets must be supplied together")
        if self.start is not None and self.end <= self.start:
            raise ValueError("End must follow start")
        return self


class ClinicalFact(Contract):
    kind: Literal["age_years", "sex", "pregnancy_status", "gestational_weeks",
                  "symptom_duration", "test"]
    value: Any = None
    unit: Optional[str] = None
    test_name: Optional[str] = None
    test_result: Optional[str] = None
    test_date: Optional[str] = None
    evidence: Optional[Evidence] = None
    extraction_method: Literal["explicit_numeric", "structured_input", "model", "unknown"]
    certainty: Literal["known", "uncertain", "unknown"]

    @model_validator(mode="after")
    def grounded_known_fact(self):
        if self.certainty != "unknown" and self.evidence is None:
            raise ValueError("Known/uncertain facts require provenance")
        return self


class Finding(Contract):
    finding_id: str = Field(min_length=1)
    type: Literal["diagnosis", "symptom", "test", "history", "other"]
    evidence: Evidence
    assertion: Literal["confirmed", "suspected", "negated", "historical", "patient_reported", "unclear"]
    encounter_relevant: Optional[bool] = None
    attributes: Dict[str, ClinicalFact] = Field(default_factory=dict)
    disposition: Literal["coded", "subsumed", "recorded_not_encounter", "unresolved"]
    reason: str = Field(min_length=1)
    assignment_code: Optional[str] = None


class DifferentialHypothesis(Contract):
    """Non-evidentiary hypothesis; never an assignment-linked finding."""
    text: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class Candidate(Contract):
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    catalogue_origin: Literal["supplied", "expanded"]
    retrieval_score: Optional[float] = None
    source: str = Field(min_length=1)
    status: Literal["supported", "rejected", "unresolved"]
    reason: str = Field(min_length=1)
    missing_discriminators: List[str] = Field(default_factory=list)


class Confidence(Contract):
    level: Literal["low", "moderate", "high"]
    increase_if: List[str] = Field(default_factory=list)
    decrease_if: List[str] = Field(default_factory=list)


class Assignment(Contract):
    code: str = Field(min_length=1)
    catalogue_origin: Literal["supplied"]
    finding_ids: List[str] = Field(min_length=1)
    evidence: List[Evidence] = Field(min_length=1)
    certainty: Literal["definitive", "provisional"]
    confidence: Confidence
    guideline_ids: List[str] = Field(default_factory=list)


class Provenance(Contract):
    mode: Literal["bootstrap", "deterministic", "model"]
    catalogue_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    guidelines_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    constraints_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_token_count: Optional[int] = Field(default=None, ge=0)


class CodingResult(Contract):
    note_id: str = Field(min_length=1)
    original_note: str
    original_record: Any = None
    input_position: Optional[int] = Field(default=None, ge=1)
    status: Literal["coded", "provisional", "unresolved"]
    assignments: List[Assignment] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    differential_hypotheses: List[DifferentialHypothesis] = Field(default_factory=list)
    candidates_considered: List[Candidate] = Field(default_factory=list)
    safety_flags: List[str] = Field(default_factory=list)
    unresolved: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confidence: Confidence
    provenance: Provenance
    facts: List[ClinicalFact] = Field(default_factory=list)
    retrieved_evidence: List["RetrievedContext"] = Field(default_factory=list)
    quarantined_note_evidence: List[Evidence] = Field(default_factory=list)
    guideline_checks: List["GuidelineCheck"] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_status(self):
        expected = "unresolved" if not self.assignments else (
            "provisional" if any(a.certainty == "provisional" for a in self.assignments) else "coded")
        if self.status != expected:
            raise ValueError("Status must reflect assignment certainty")
        return self


class RetrievedContext(Contract):
    source_type: Literal["catalogue", "guideline"]
    source_id: str
    title: str
    retrieval_score: float = Field(ge=0)
    source_quote: str
    raw_text: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    warnings: List[str] = Field(default_factory=list)


class GuidelineCheck(Contract):
    source_id: str
    record_id: str
    verification_status: Literal["verified", "uncertain", "rejected"]
    outcomes: Dict[str, Literal["met", "not_met", "unknown"]]


CodingResult.model_rebuild()
