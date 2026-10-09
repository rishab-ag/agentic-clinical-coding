"""Model wire contracts exclude application-owned input, hashes and status."""
from typing import List, Literal, Optional, Union
import math
from pydantic import model_validator

from app.models import (Assignment, Candidate, Confidence, Contract, DifferentialHypothesis,
                        Evidence)


class ExtractedFinding(Contract):
    finding_id: str
    type: Literal["diagnosis", "symptom", "test", "history", "other"]
    evidence: Evidence
    assertion: Literal["confirmed", "suspected", "negated", "historical", "patient_reported", "unclear"]
    encounter_relevant: Optional[bool]
    temporality: Literal["current", "historical", "unknown"]
    experiencer: Literal["patient", "other", "unknown"]


class ExtractedFact(Contract):
    kind: Literal["age_years", "sex", "pregnancy_status", "gestational_weeks", "symptom_duration", "test"]
    value: Union[str, float, bool, None]
    unit: Optional[str]
    test_name: Optional[str]
    test_result: Optional[str]
    test_date: Optional[str]
    evidence: Evidence
    certainty: Literal["known", "uncertain", "unknown"]

    @model_validator(mode="after")
    def finite_value(self):
        if type(self.value) is float and not math.isfinite(self.value):
            raise ValueError("Fact values must be finite")
        if self.certainty=="known" and self.kind in ("age_years","gestational_weeks","symptom_duration") and type(self.value) is not float:
            raise ValueError("Known numeric facts require numeric values")
        return self


class ExtractedFindings(Contract):
    findings: List[ExtractedFinding]
    facts: List[ExtractedFact]
    differential_hypotheses: List[DifferentialHypothesis]


class FindingDisposition(Contract):
    finding_id: str
    disposition: Literal["coded", "subsumed", "recorded_not_encounter", "unresolved"]
    reason: str
    assignment_code: Optional[str]


class RequirementAssessment(Contract):
    source: Evidence
    applies_to: Literal["definitive", "provisional", "all"]
    outcome: Literal["met", "not_met", "unknown"]
    evidence: List[Evidence]
    explanation: str


class GuidelineAssessment(Contract):
    source_id: str
    applicability: Literal["met", "not_met", "unknown"]
    explanation: str
    requirements: List[RequirementAssessment]


class DecisionProposal(Contract):
    assignments: List[Assignment]
    dispositions: List[FindingDisposition]
    candidates_considered: List[Candidate]
    guideline_review: List[GuidelineAssessment]
    safety_flags: List[str]
    unresolved: List[str]
    warnings: List[str]
    confidence: Confidence
