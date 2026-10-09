"""Human-owned evaluation contracts and saved-result grading.

This module does not generate notes, labels, prompts, or clinical decisions.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Literal, Optional, Union

from pydantic import AliasChoices, Field, model_validator

from app.data import SuppliedData, load_supplied_data
from app.models import CodingResult, Contract, Note
from app.eval_checks import ExecutableConditionalExpectation, evaluate_check, evaluate_predicate, conditional_schema_issues

DEFAULT_FIXTURES = Path(__file__).resolve().parent.parent / "tests/fixtures/clinical_eval.jsonl"


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


class AcceptableOutcome(Contract):
    status: Literal["coded", "provisional", "unresolved"]
    required_codes: List[str] = Field(default_factory=list)
    forbidden_codes: List[str] = Field(default_factory=list)
    allowed_code_sets: Optional[List[List[str]]] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def coherent_codes(self):
        if set(self.required_codes).intersection(self.forbidden_codes):
            raise ValueError("Required outcome codes cannot be forbidden")
        if self.status == "unresolved" and self.required_codes:
            raise ValueError("Unresolved outcomes cannot require assignments")
        if self.allowed_code_sets is not None:
            for codes in self.allowed_code_sets:
                if len(codes) != len(set(codes)) or not set(self.required_codes).issubset(codes) or set(codes).intersection(self.forbidden_codes):
                    raise ValueError("Allowed code set conflicts with outcome requirements")
                if (self.status == "unresolved") != (not codes):
                    raise ValueError("Allowed code set conflicts with status")
        return self


class ExpectedFinding(Contract):
    source_quote: str = Field(min_length=1)
    assertion: Literal["confirmed", "suspected", "negated", "historical", "patient_reported", "unclear"]
    allowed_dispositions: List[Literal["coded", "subsumed", "recorded_not_encounter", "unresolved"]] = Field(min_length=1)


class ExpectedCandidate(Contract):
    code: str = Field(min_length=1)
    catalogue_origin: Literal["supplied", "expanded"]
    required_missing_discriminators: List[str] = Field(default_factory=list)


class Expectations(Contract):
    required_codes: List[str] = Field(default_factory=list)
    forbidden_codes: List[str] = Field(default_factory=list)
    required_safety_flags: List[str] = Field(default_factory=list)
    expected_findings: List[ExpectedFinding] = Field(default_factory=list)
    required_candidates: List[ExpectedCandidate] = Field(default_factory=list)
    required_explanations: List[str] = Field(default_factory=list)
    required_guideline_ids: List[str] = Field(default_factory=list)


class ConditionalExpectation(Expectations):
    when_status: Optional[Literal["coded", "provisional", "unresolved"]] = None
    when_all_codes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def explicit_trigger(self):
        if self.when_status is None and not self.when_all_codes:
            raise ValueError("Conditional expectation requires a status or code trigger")
        if set(self.required_codes).intersection(self.forbidden_codes):
            raise ValueError("Conditional required and forbidden codes conflict")
        return self


class AdvisoryConditionalExpectation(Contract):
    """Retain human draft prose without pretending to execute its clinical meaning."""
    if_text: str = Field(alias="if", min_length=1)
    then_text: str = Field(alias="then", min_length=1)


class FixtureReviewMetadata(Contract):
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_status: Literal["human_approved", "pending_review", "pending_human_review", "rejected"]
    review_notes: str


class HumanFixture(Expectations):
    note_id: str = Field(min_length=1)
    note_text: str = Field(min_length=1)
    split: Literal["development", "held_out"] = Field(default="development", validation_alias=AliasChoices("split", "evaluation_split"))
    review_status: Literal["human_approved", "pending_review", "pending_human_review", "rejected"]
    reviewed_by: Optional[str] = Field(default=None, min_length=1)
    reviewed_at: Optional[str] = Field(default=None, min_length=1)
    rationale: Optional[str] = Field(default=None, min_length=1)
    title: Optional[str] = None
    catalogue_basis: Optional[str] = None
    review_rationale: Optional[str] = None
    review_metadata: Optional[FixtureReviewMetadata] = None
    acceptable_statuses: List[Literal["coded", "provisional", "unresolved"]]
    required_codes: List[str]
    forbidden_codes: List[str]
    relevant_guideline_ids: List[str]
    acceptable_outcomes: List[AcceptableOutcome] = Field(default_factory=list)
    conditional_expectations: List[Union[ConditionalExpectation, ExecutableConditionalExpectation, AdvisoryConditionalExpectation]] = Field(default_factory=list)
    coverage_tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent_rubric(self):
        if self.review_metadata and self.review_metadata.review_status != self.review_status:
            raise ValueError("Top-level and nested review statuses conflict")
        reviewer = self.reviewed_by or (self.review_metadata.reviewer if self.review_metadata else None)
        reviewed_at = self.reviewed_at or (self.review_metadata.reviewed_at if self.review_metadata else None)
        if self.review_status == "human_approved" and (not self.acceptable_statuses or not reviewer or not reviewed_at or not (self.rationale or self.review_rationale)):
            raise ValueError("Human-approved fixtures require statuses and actual independent review metadata")
        if self.review_status == "human_approved" and any(isinstance(c, AdvisoryConditionalExpectation) for c in self.conditional_expectations):
            raise ValueError("Human-approved conditional prose must be translated by the human into executable expectations before scoring")
        if set(self.required_codes).intersection(self.forbidden_codes):
            raise ValueError("Required assignment cannot also be forbidden")
        if self.required_codes and "unresolved" in self.acceptable_statuses:
            raise ValueError("Use conditional required codes when unresolved is acceptable")
        for outcome in self.acceptable_outcomes:
            if outcome.status not in self.acceptable_statuses:
                raise ValueError("Outcome status is not in acceptable_statuses")
            if set(outcome.required_codes).intersection(self.forbidden_codes):
                raise ValueError("Outcome required code is globally forbidden")
        for group in [self] + [c for c in self.conditional_expectations if isinstance(c, ConditionalExpectation)]:
            quotes = [normalized(f.source_quote) for f in group.expected_findings]
            if len(quotes) != len(set(quotes)):
                raise ValueError("Expected finding quotes must be unique within each expectation group")
            if any(not quote or quote not in normalized(self.note_text) for quote in quotes):
                raise ValueError("Expected finding quotes must occur in the human-owned note")
        return self


class FixtureSet(Contract):
    schema_version: Literal[1] = 1
    fixtures: List[HumanFixture]

    @model_validator(mode="after")
    def unique_ids(self):
        if len({f.note_id for f in self.fixtures}) != len(self.fixtures):
            raise ValueError("Fixture note IDs must be unique")
        return self


def load_fixtures(path: Path, data: SuppliedData) -> FixtureSet:
    if path.suffix.lower() == ".jsonl":
        fixtures = FixtureSet.model_validate(dict(schema_version=1, fixtures=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]))
    else:
        fixtures = FixtureSet.model_validate_json(path.read_bytes())
    supplied_codes = {entry.code for entry in data.catalogue}
    guideline_ids = {entry.id for entry in data.guidelines}
    for fixture in fixtures.fixtures:
        if set(fixture.relevant_guideline_ids) - guideline_ids:
            raise ValueError(f"{fixture.note_id}: unknown relevant guideline ID")
        for group in [fixture] + [c for c in fixture.conditional_expectations if isinstance(c, ConditionalExpectation)] + fixture.acceptable_outcomes:
            allowed_codes = set(group.required_codes)
            if isinstance(group, AcceptableOutcome) and group.allowed_code_sets is not None:
                allowed_codes.update(c for codes in group.allowed_code_sets for c in codes)
            if allowed_codes - supplied_codes:
                raise ValueError(f"{fixture.note_id}: required/allowed assignment code outside supplied catalogue")
            if isinstance(group, Expectations):
                if set(group.required_guideline_ids) - guideline_ids:
                    raise ValueError(f"{fixture.note_id}: unknown required guideline ID")
                if any(c.catalogue_origin == "supplied" and c.code not in supplied_codes for c in group.required_candidates):
                    raise ValueError(f"{fixture.note_id}: required supplied candidate outside supplied catalogue")
    return fixtures


def _explanation_text(result: CodingResult) -> str:
    # Only explanation-bearing fields count, not quotes copied from the note.
    parts = list(result.unresolved) + list(result.warnings) + list(result.safety_flags)
    parts += result.confidence.increase_if + result.confidence.decrease_if
    parts += [f.reason for f in result.findings]
    for candidate in result.candidates_considered:
        parts += [candidate.reason] + candidate.missing_discriminators
    return normalized("\n".join(parts))


def grade_fixture(fixture: HumanFixture, raw: Any, data: SuppliedData) -> Dict[str, Any]:
    """Grade one supplied decision against human labels; never decide clinically."""
    if fixture.review_status != "human_approved":
        raise ValueError("Only human_approved fixtures may be scored")
    errors = []
    try:
        result = CodingResult.model_validate(raw.model_dump() if isinstance(raw, CodingResult) else raw)
    except ValueError:
        return dict(note_id=fixture.note_id, passed=False, errors=["Invalid CodingResult schema"],
                    status_agrees=False, expected_findings=len(fixture.expected_findings),
                    matched_findings=0, disposition_matches=0, high_confidence=False)
    if result.note_id != fixture.note_id:
        errors.append("Result ID differs from fixture ID")
    if result.original_note != fixture.note_text:
        errors.append("Original note differs from immutable fixture")
    actual_codes = {a.code for a in result.assignments}
    if len(actual_codes) != len(result.assignments):
        errors.append("Duplicate assignments")
    status_agrees = result.status in fixture.acceptable_statuses
    if not status_agrees:
        errors.append("Status outside human-approved acceptable statuses")
    if fixture.acceptable_outcomes and not any(o.status == result.status and
            set(o.required_codes).issubset(actual_codes) and not actual_codes.intersection(o.forbidden_codes) and
            (o.allowed_code_sets is None or any(set(codes) == actual_codes for codes in o.allowed_code_sets))
            for o in fixture.acceptable_outcomes):
        errors.append("Decision outside human-approved alternative outcomes")
    groups = [fixture] + [group for group in fixture.conditional_expectations
        if isinstance(group, ConditionalExpectation) and (group.when_status is None or group.when_status == result.status) and set(group.when_all_codes).issubset(actual_codes)]
    result_payload = result.model_dump()
    for index, conditional in enumerate(fixture.conditional_expectations, 1):
        if not isinstance(conditional, ExecutableConditionalExpectation):
            continue
        schema_errors = conditional_schema_issues(conditional)
        if schema_errors:
            errors.extend(f"Conditional expectation {index}: {issue}" for issue in schema_errors)
            continue
        trigger = evaluate_predicate(conditional.when, result_payload)
        if trigger == "unknown":
            errors.append(f"Conditional expectation {index}: trigger unknown")
        elif trigger == "met":
            for check_index, check in enumerate(conditional.checks, 1):
                outcome = evaluate_check(check, result_payload, fixture.note_id, fixture.note_text)
                if outcome != "met":
                    errors.append(f"Conditional expectation {index}, check {check_index}: {outcome}")
    required_codes = {code for group in groups for code in group.required_codes}
    forbidden_codes = {code for group in groups for code in group.forbidden_codes}
    if required_codes - actual_codes:
        errors.append("Missing human-required assignment code")
    if actual_codes.intersection(forbidden_codes):
        errors.append("Forbidden assignment code present")
    codes = {c.code for c in data.catalogue}
    guidelines = {g.id for g in data.guidelines}
    cited = set()
    for assignment in result.assignments:
        if assignment.code not in codes:
            errors.append("Assignment code outside supplied catalogue")
        cited.update(assignment.guideline_ids)
        for evidence in assignment.evidence:
            if evidence.source_type == "guideline":
                cited.add(evidence.source_id)
            elif evidence.source_type == "catalogue" and evidence.source_id not in codes:
                errors.append("Unknown catalogue evidence code")
        # This is an evaluation diagnostic, not the future runtime validator.
        if not any(e.source_type == "note" and normalized(e.source_quote).strip() and normalized(e.source_quote) in normalized(fixture.note_text)
                   and e.source_id == fixture.note_id for e in assignment.evidence):
            errors.append("Assignment lacks original-note quote")
    if cited - guidelines:
        errors.append("Unknown guideline citation")
    if {code for group in groups for code in group.required_guideline_ids} - cited:
        errors.append("Missing human-required guideline citation")
    if {normalized(flag) for group in groups for flag in group.required_safety_flags} - set(map(normalized, result.safety_flags)):
        errors.append("Missing human-required safety flag")
    matched = 0
    disposition_matches = 0
    expected_findings = [expected for group in groups for expected in group.expected_findings]
    for expected in expected_findings:
        candidates = [f for f in result.findings if normalized(f.evidence.source_quote) == normalized(expected.source_quote)
                      and f.evidence.source_type == "note" and f.evidence.source_id == fixture.note_id]
        if candidates:
            matched += 1
        if len(candidates) != 1:
            errors.append("Expected finding missing or duplicated")
        elif candidates[0].assertion != expected.assertion or candidates[0].disposition not in expected.allowed_dispositions:
            errors.append("Finding assertion/disposition outside human rubric")
        else:
            disposition_matches += 1
    for expected in [expected for group in groups for expected in group.required_candidates]:
        candidates = [c for c in result.candidates_considered if c.code == expected.code and c.catalogue_origin == expected.catalogue_origin]
        if not candidates or not any(set(map(normalized, expected.required_missing_discriminators)).issubset(
                set(map(normalized, c.missing_discriminators))) for c in candidates):
            errors.append("Missing human-required candidate/discriminators")
    explanations = _explanation_text(result)
    if any(not normalized(text) or normalized(text) not in explanations for group in groups for text in group.required_explanations):
        errors.append("Missing human-required explanation")
    return dict(note_id=fixture.note_id, passed=not errors, errors=errors, status_agrees=status_agrees,
                expected_findings=len(expected_findings), matched_findings=matched,
                disposition_matches=disposition_matches,
                high_confidence=result.confidence.level == "high" or any(a.confidence.level == "high" for a in result.assignments))


def evaluate_results(fixtures: List[HumanFixture], results: List[Any], data: SuppliedData) -> Dict[str, Any]:
    skipped = [f.note_id for f in fixtures if f.review_status != "human_approved"]
    fixtures = [f for f in fixtures if f.review_status == "human_approved"]
    if not fixtures:
        raise ValueError("No human_approved fixtures selected; human labels are required")
    if len({f.note_id for f in fixtures}) != len(fixtures):
        raise ValueError("Duplicate fixture IDs cannot be scored")
    by_id = defaultdict(list)
    run_errors = []
    for position, result in enumerate(results, 1):
        note_id = result.note_id if isinstance(result, CodingResult) else (result.get("note_id") if isinstance(result, dict) else None)
        if not isinstance(note_id, str) or not note_id:
            run_errors.append(f"Result record {position} has no valid note_id")
        else:
            by_id[note_id].append(result)
    expected_ids = {f.note_id for f in fixtures}
    extra_ids = sorted(set(by_id) - expected_ids)
    if extra_ids:
        run_errors.append("Unexpected result IDs outside selected fixture split")
    cases = []
    for fixture in fixtures:
        rows = by_id.get(fixture.note_id, [])
        if len(rows) != 1:
            cases.append(dict(note_id=fixture.note_id, passed=False, errors=[f"Expected one result, received {len(rows)}"],
                              status_agrees=False, expected_findings=len(fixture.expected_findings), matched_findings=0,
                              disposition_matches=0, high_confidence=False))
        else:
            cases.append(grade_fixture(fixture, rows[0], data))
    finding_count = sum(c["expected_findings"] for c in cases)
    return dict(type="evaluation_report", evaluation_kind="saved_results_against_human_rubric",
                passed=not run_errors and all(c["passed"] for c in cases), cases=cases,
                run_errors=run_errors, unexpected_note_ids=extra_ids, unscored_fixture_ids=skipped,
                metrics=dict(expected_notes=len(fixtures), result_records=len(results),
                    notes_with_exactly_one_result=sum(len(by_id[f.note_id]) == 1 for f in fixtures),
                    note_coverage=sum(bool(by_id[f.note_id]) for f in fixtures) / len(fixtures),
                    rubric_matches=sum(c["passed"] for c in cases),
                    status_matches=sum(c["status_agrees"] for c in cases),
                    expected_findings=finding_count, matched_findings=sum(c["matched_findings"] for c in cases),
                    expected_finding_coverage=(sum(c["matched_findings"] for c in cases) / finding_count if finding_count else None),
                    disposition_matches=sum(c["disposition_matches"] for c in cases),
                    high_confidence_rubric_failures=sum(c["high_confidence"] and not c["passed"] for c in cases)))


def evaluate_callable(fixtures: List[HumanFixture], decide: Callable[[Note], CodingResult], data: SuppliedData) -> Dict[str, Any]:
    """Pytest helper for a future pipeline; isolate failures without inventing decisions."""
    results = []
    failures = []
    for fixture in fixtures:
        if fixture.review_status != "human_approved":
            continue
        try:
            results.append(decide(Note(note_id=fixture.note_id, text=fixture.note_text)))
        except Exception:
            # Do not leak raw clinical text, secrets, or provider exception payloads.
            failures.append(f"Pipeline raised for fixture {fixture.note_id}")
    report = evaluate_results(fixtures, results, data)
    report["run_errors"].extend(failures)
    report["passed"] = report["passed"] and not failures
    return report


def read_result_lines(path: Path) -> List[Any]:
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            results.append(json.loads(line))
        except ValueError:
            results.append(None)  # Account for malformed/blank records in run_errors.
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate saved CodingResult JSONL against human-approved fixtures")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--results", type=Path, help="Saved results; required only when scoring approved fixtures")
    parser.add_argument("--validate-fixtures", action="store_true", help="Validate fixture structure without clinical scoring")
    parser.add_argument("--split", choices=["development", "held_out", "all"], default="development")
    args = parser.parse_args(argv)
    try:
        data = load_supplied_data()
        fixture_set = load_fixtures(args.fixtures, data)
        approved = [f for f in fixture_set.fixtures if f.review_status == "human_approved"]
        inventory = dict(fixture_count=len(fixture_set.fixtures), approved_fixture_count=len(approved),
                         fixtures_sha256=hashlib.sha256(args.fixtures.read_bytes()).hexdigest(),
                         fixture_gate_met=len(approved) >= 10 and sum(f.split == "held_out" for f in approved) >= 2,
                         review_counts={status: sum(f.review_status == status for f in fixture_set.fixtures)
                                        for status in ("human_approved", "pending_human_review", "pending_review", "rejected")})
        inventory["split_counts"] = {split: sum(f.split == split for f in fixture_set.fixtures) for split in ("development", "held_out")}
        inventory["infrastructure_issues"] = [
            dict(note_id=f.note_id, issues=(
                (["Split omitted; current schema defaults to development"] if "split" not in f.model_fields_set else []) +
                (["Reviewer/time approval metadata incomplete"] if not (f.reviewed_by or (f.review_metadata and f.review_metadata.reviewer)) or not (f.reviewed_at or (f.review_metadata and f.review_metadata.reviewed_at)) else []) +
                (["Prose conditional expectations require explicit selectors/checks; no clinical alias inference"]
                 if any(isinstance(c, AdvisoryConditionalExpectation) for c in f.conditional_expectations) else []) +
                [issue for c in f.conditional_expectations if isinstance(c, ExecutableConditionalExpectation)
                 for issue in conditional_schema_issues(c)]))
            for f in fixture_set.fixtures]
        if args.validate_fixtures:
            print(json.dumps(dict(type="fixture_validation", status="validated", clinical_scoring=False, **inventory)))
            return 0
        selected = [f for f in fixture_set.fixtures if args.split == "all" or f.split == args.split]
        if not selected:
            raise ValueError("No human_approved fixtures selected; human labels are required or the selected split is empty")
        if not any(f.review_status == "human_approved" for f in selected):
            print(json.dumps(dict(type="evaluation_report", status="skipped", passed=None, metrics=None,
                                  reason="No human_approved fixtures selected; human labels are required",
                                  clinical_scoring=False, split=args.split,
                                  unscored_fixture_ids=[f.note_id for f in selected], **inventory)))
            return 0
        if args.results is None:
            raise ValueError("--results is required to score human_approved fixtures")
        report = evaluate_results(selected, read_result_lines(args.results), data)
        report["split"] = args.split
        report["fixtures_sha256"] = hashlib.sha256(args.fixtures.read_bytes()).hexdigest()
        report["results_sha256"] = hashlib.sha256(args.results.read_bytes()).hexdigest()
        report["fixture_gate_met"] = len(approved) >= 10 and sum(f.split == "held_out" for f in approved) >= 2
        report["approved_fixture_count"] = len(approved)
        report["coverage_tags"] = sorted({tag for f in selected for tag in f.coverage_tags})
    except (OSError, ValueError) as error:
        print(f"Evaluation cannot run: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
