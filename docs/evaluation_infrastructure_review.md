# Evaluation infrastructure review — no clinical approval

The updated `tests/fixtures/clinical_eval.jsonl` and
`docs/clinical_fixture_review.md` are human-owned inputs and are not edited by
the runner. The ten records remain pending, with seven development and three
held-out cases. Nested reviewer/time values are null; no approval is inferred.
All guideline drafts remain unverified.

Implemented mechanical checks against CodingResult include nested predicates,
assignment certainty/confidence/citations, original-note quote/offset checks,
and confirmed encounter-relevant finding linkage. Arrays require explicit
element predicates. These are generic capabilities, not enabled clinical labels.
Malformed output paths fail scoring even if a trigger would otherwise be false.
Prose conditions remain advisory and block approval-based scoring until made
explicit by the human; the software does not invent their clinical meaning.

Outstanding format/expectation issues in the supplied packet:

- `assignment_status` is not an Assignment field. The output field is `certainty`
  (`definitive`/`provisional`); note status is `status`.
- `confidence!=high` needs a specified scope: note confidence, per-assignment
  confidence, or both. Each is an object with a `level` field.
- Disease-named triggers such as `pneumonia_assigned`, `tonsillitis_assigned`,
  `diabetes_type_assigned`, and `any_sepsis_assignment` need explicit output
  selectors. No code sets are inferred from these names.
- “Missing imaging” needs an explicit candidate/discriminator requirement.
  Candidate retrieval scores and candidate presence never imply assignment.
- `candidate_provided` is not code-specific, and “may be considered” is not
  an obligation. Candidates have `status`, not a `confirmed` assertion field.
- Explicit *applicable* provisional permission cannot be established by a
  citation ID alone. Its clinical applicability requires human review; no
  unrestricted regex permission check is added.
- “Confirmed history” must be reconciled with the contract requiring confirmed,
  encounter-relevant evidence for definitive assignments. Historical findings
  alone cannot satisfy the confirmed encounter linkage check.
- `directive_followed` needs an observable output predicate; an evaluator cannot
  infer the model's causal behavior. Supplied forbidden-code expectations remain
  separately enforceable when approved.
- Proposed safety-flag strings have no implemented clinical flag producer yet.
  The evaluator supports exact strings; taxonomy agreement needs review.
- The packet's blanket confirmed-finding requirement for *every* assignment
  needs reconciliation with its provisional alternatives. No clinical
  interpretation or label correction is made by this infrastructure change.

These issues are reported for human resolution. They are not approval decisions
or expected-label changes. Pending fixtures produce a skip with no clinical
metrics. Structured predicates can be tested on non-clinical dummy outputs;
no clinical notes are scored in the structural suite.
