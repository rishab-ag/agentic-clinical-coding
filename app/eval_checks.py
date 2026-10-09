"""Declarative output checks; no clinical names, codes, or prose interpretation."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from app.models import Contract
from app.models import CodingResult

Outcome = Literal["met", "not_met", "unknown"]


class OutputPredicate(Contract):
    path: Optional[str] = None
    operator: Optional[Literal["eq", "ne", "in", "not_in", "contains", "exists", "absent", "any", "all", "none"]] = None
    value: Any = None
    item: Optional["OutputPredicate"] = None
    all_of: Optional[List["OutputPredicate"]] = Field(default=None, min_length=1)
    any_of: Optional[List["OutputPredicate"]] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def unambiguous_expression(self):
        composite = self.all_of is not None or self.any_of is not None
        if composite:
            if (self.all_of is not None and self.any_of is not None) or self.path is not None or self.operator is not None or self.item is not None:
                raise ValueError("Use one predicate form: all_of, any_of, or path/operator")
        elif not self.path or not self.operator:
            raise ValueError("Leaf predicates require path and operator")
        elif self.operator in ("any", "all", "none"):
            if self.item is None:
                raise ValueError("Collection predicates require an item predicate")
        elif self.item is not None:
            raise ValueError("Only collection predicates accept item")
        elif self.operator not in ("exists", "absent") and "value" not in self.model_fields_set:
            raise ValueError("Comparison predicates require an explicit value")
        if self.operator in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError("Membership value must be a list")
        if self.path and any(not part or part.startswith("_") for part in self.path.split(".")):
            raise ValueError("Paths are dotted public JSON field names")
        return self


OutputPredicate.model_rebuild()


class OutputCheck(Contract):
    kind: Literal["predicate", "original_note_evidence", "confirmed_encounter_link"]
    predicate: Optional[OutputPredicate] = None
    assignment_filter: Optional[OutputPredicate] = None

    @model_validator(mode="after")
    def check_contract(self):
        if self.kind == "predicate":
            if self.predicate is None or self.assignment_filter is not None:
                raise ValueError("Predicate check requires only predicate")
        elif self.predicate is not None:
            raise ValueError("Assignment evidence checks accept assignment_filter, not predicate")
        return self


class ExecutableConditionalExpectation(Contract):
    when: OutputPredicate
    checks: List[OutputCheck] = Field(min_length=1)


def _combine(values: List[Outcome], mode: str) -> Outcome:
    if not values:
        return "unknown"
    if mode == "all":
        return "not_met" if "not_met" in values else ("unknown" if "unknown" in values else "met")
    return "met" if "met" in values else ("unknown" if "unknown" in values else "not_met")


def evaluate_predicate(predicate: OutputPredicate, context: Any) -> Outcome:
    if predicate.all_of is not None:
        return _combine([evaluate_predicate(p, context) for p in predicate.all_of], "all")
    if predicate.any_of is not None:
        return _combine([evaluate_predicate(p, context) for p in predicate.any_of], "any")
    current = context
    missing = False
    for key in predicate.path.split("."):
        if not isinstance(current, dict) or key not in current:
            missing = True
            break
        current = current[key]
    if predicate.operator == "exists":
        return "not_met" if missing or current is None else "met"
    if predicate.operator == "absent":
        return "met" if missing or current is None else "not_met"
    if missing:
        return "unknown"
    if predicate.operator in ("any", "all", "none"):
        if not isinstance(current, list):
            return "unknown"
        values = [evaluate_predicate(predicate.item, item) for item in current]
        if predicate.operator == "all":
            return _combine(values, "all")
        value = _combine(values, "any") if values else "not_met"
        if predicate.operator == "none":
            return {"met": "not_met", "not_met": "met", "unknown": "unknown"}[value]
        return value
    if predicate.operator in ("eq", "ne"):
        # JSON booleans must not be equal to numeric 0/1 in a rubric.
        equal = type(current) == type(predicate.value) and current == predicate.value
        return "met" if (equal if predicate.operator == "eq" else not equal) else "not_met"
    if predicate.operator in ("in", "not_in"):
        member = any(type(current) == type(v) and current == v for v in predicate.value)
        return "met" if (member if predicate.operator == "in" else not member) else "not_met"
    if predicate.operator == "contains":
        if isinstance(current, str) and isinstance(predicate.value, str):
            return "met" if predicate.value in current else "not_met"
        if isinstance(current, list):
            return "met" if any(type(v) == type(predicate.value) and v == predicate.value for v in current) else "not_met"
    return "unknown"


def _grounded(evidence: Dict[str, Any], note_id: str, note_text: str) -> bool:
    normalize = lambda text: " ".join(text.casefold().split())
    quote = evidence.get("source_quote")
    if evidence.get("source_type") != "note" or evidence.get("source_id") != note_id or not isinstance(quote, str) or not normalize(quote):
        return False
    if normalize(quote) not in normalize(note_text):
        return False
    start, end = evidence.get("start"), evidence.get("end")
    if start is None and end is None:
        return True
    return type(start) is int and type(end) is int and 0 <= start < end <= len(note_text) and normalize(note_text[start:end]) == normalize(quote)


def evaluate_check(check: OutputCheck, result: Dict[str, Any], note_id: str, note_text: str) -> Outcome:
    if check.kind == "predicate":
        return evaluate_predicate(check.predicate, result)
    selected = []
    for assignment in result["assignments"]:
        outcome = evaluate_predicate(check.assignment_filter, assignment) if check.assignment_filter else "met"
        if outcome == "unknown":
            return "unknown"
        if outcome == "met":
            selected.append(assignment)
    if not selected:
        return "unknown"  # An evidence check cannot pass without an assignment.
    for assignment in selected:
        if check.kind == "original_note_evidence":
            if not any(_grounded(e, note_id, note_text) for e in assignment["evidence"]):
                return "not_met"
        else:
            linked = [f for f in result["findings"] if f["finding_id"] in assignment["finding_ids"]]
            if not any(f["assertion"] == "confirmed" and f["encounter_relevant"] is True and
                       _grounded(f["evidence"], note_id, note_text) for f in linked):
                return "not_met"
    return "met"


def predicate_schema_issues(predicate: OutputPredicate, schema: Optional[Dict[str, Any]] = None) -> List[str]:
    """Check predicate paths against CodingResult's schema, without clinical interpretation."""
    root = CodingResult.model_json_schema()
    def resolve(node):
        if "$ref" in node:
            return root["$defs"][node["$ref"].split("/")[-1]]
        if "anyOf" in node:
            options = [n for n in node["anyOf"] if n.get("type") != "null"]
            return resolve(options[0]) if len(options) == 1 else node
        return node
    context = resolve(schema or root)
    if predicate.all_of is not None or predicate.any_of is not None:
        return [issue for p in (predicate.all_of or predicate.any_of)
                for issue in predicate_schema_issues(p, context)]
    for part in predicate.path.split("."):
        context = resolve(context)
        if part not in context.get("properties", {}):
            return [f"Unknown output path {predicate.path}; arrays require item predicates"]
        context = context["properties"][part]
    context = resolve(context)
    if predicate.operator in ("any", "all", "none"):
        if context.get("type") != "array":
            return [f"Collection operator on non-array path {predicate.path}"]
        return predicate_schema_issues(predicate.item, context["items"])
    return []


def conditional_schema_issues(conditional: ExecutableConditionalExpectation) -> List[str]:
    issues = predicate_schema_issues(conditional.when)
    assignment_schema = CodingResult.model_json_schema()["$defs"]["Assignment"]
    for check in conditional.checks:
        if check.predicate:
            issues.extend(predicate_schema_issues(check.predicate))
        if check.assignment_filter:
            issues.extend(predicate_schema_issues(check.assignment_filter, assignment_schema))
    return issues
