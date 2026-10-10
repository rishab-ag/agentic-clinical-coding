# Milestone 3: human-owned evaluation

The current fixture file contains four reviewer-marked approved records and six
pending records. Codex has drafted executable conditions for the six pending
records at the user's request; these are AI-proposed, not independently approved.
See [the proposal review packet](fixture_expectation_proposals.md) for selectors,
original prose, authorship and unresolved interpretations. The ten-fixture gate
remains deferred. Pending records are never clinically scored.

Copy the template to `eval/fixtures.json`. Its root is:

```json
{"schema_version": 1, "fixtures": []}
```

Every fixture must explicitly contain these core fields:

| Field | Format |
|---|---|
| `note_id` | Unique nonempty string |
| `note_text` | Immutable human-owned synthetic note |
| `acceptable_statuses` | List selected by the human from `coded`, `provisional`, `unresolved` |
| `required_codes` | Assignment codes that must be present; subset, not exact set |
| `forbidden_codes` | Assignment codes that must be absent |
| `relevant_guideline_ids` | Source IDs supporting human review; not automatically required citations |
| `review_status` | `pending_review`, `pending_human_review`, `human_approved`, or `rejected` |

For `human_approved`, nonempty acceptable statuses and actual `reviewed_by`,
`reviewed_at` and `rationale` are required. These are human attestations, not
certifications the software can authenticate. Pending/rejected fixtures are never
scored or sent to the callable runner. No selected human-approved fixtures causes
an explicit skip with `passed: null` and `metrics: null`, never a vacuous pass.
An empty fixture file or selected split is an error. Do not use real patient data or secrets.
JSONL files are also supported: one fixture object per line without a root wrapper.
Blank/malformed fixture lines are errors rather than silently skipped records.
Draft metadata `title`, `catalogue_basis` and `review_rationale` are retained;
the latter may supply the approved rationale alongside actual reviewer/time.

Optional fields:

| Field | Format |
|---|---|
| `split` | `development` (default) or `held_out` |
| `coverage_tags` | Human-selected test dimensions |
| `acceptable_outcomes` | Alternative objects with `status`, optional `required_codes`, `forbidden_codes`, and `allowed_code_sets` |
| `required_safety_flags` | Required exact strings, case/whitespace normalized |
| `expected_findings` | Objects with `source_quote`, `assertion`, `allowed_dispositions` |
| `required_candidates` | Objects with `code`, `catalogue_origin`, `required_missing_discriminators` |
| `required_explanations` | Human-selected explanation substrings |
| `required_guideline_ids` | Citations that must actually appear in assignments/evidence |
| `conditional_expectations` | Objects with a trigger and any of the expectation fields above except alternative outcomes |

`acceptable_statuses` permits multiple defensible statuses. If supplied,
`acceptable_outcomes` further restricts them through alternative rubrics; any
one alternative may satisfy that portion. Code requirements are subsets unless
a human explicitly supplies `allowed_code_sets` (lists of exact unordered code
sets). An unresolved alternative cannot require assignment codes. Required and
forbidden assignment codes cannot conflict. Required/allowed assignment codes
must exist in the supplied catalogue. Expanded-only candidates remain candidates.

A conditional expectation has `when_status` and/or `when_all_codes`. Both must
match if both are present; at least one trigger is required. Its requirements
apply only to matching output decisions. Use this for different obligations on
coded, provisional or unresolved alternatives. Conditions do not parse the note
or infer medical criteria. Global expectations apply to every alternative, so
put outcome-dependent code/citation requirements in conditional groups.
Draft prose `{ "if": "...", "then": "..." }` is preserved for human review,
but cannot be scored after approval until it is converted to explicit
machine-checkable expectations and independently reviewed. The runner does not invent a clinical meaning
for conditional prose or silently ignore it.

Executable conditions also accept `when` (an output predicate) and `checks`
(a nonempty list). Predicates use actual output paths, `operator` and `value`.
Supported operators: `eq`, `ne`, `in`, `not_in`, `contains`, `exists`, `absent`,
and array `any`/`all`/`none` with an `item` predicate relative to each element.
`all_of`/`any_of` combine nonempty predicate lists. Missing comparison paths or
incompatible values return unknown; an unknown conditional trigger/check fails
evaluation rather than silently skipping an obligation. Empty `all` is unknown.

Checks are `predicate`, `original_note_evidence`, or `confirmed_encounter_link`.
The last two apply to assignments, optionally selected with `assignment_filter`.
They verify immutable fixture quotes/offsets and, for confirmed links, confirmed
encounter-relevant linked findings. They do not establish clinical diagnosis or
interpret guideline permission. Assignment certainty is `assignments[].certainty`,
not `assignment_status`; confidence is `confidence.level`. Use `item` to check
array members; path strings do not support wildcards or arbitrary Python code.
Clinical aliases such as a named disease “assigned” require explicitly provided
selectors; the runner never invents disease-to-code mappings from prose.

Validation reports list missing split/reviewer metadata and uncompiled prose
expectations without editing them. Missing split currently defaults to development;
an explicitly supplied held-out split is preserved. This report is not approval.
The packet's `evaluation_split` is accepted as a validation alias for `split`.
Nested `review_metadata` is retained unchanged; its status must agree with the
top-level review status. Approval uses actual nested reviewer/time (or existing
flat fields) and never upgrades a pending record. Explicit output predicates
are checked against the actual CodingResult schema during validation; invalid
paths are reported. No source/fixture file is rewritten by this workflow.

Finding quotes must occur in the human note with only case/whitespace
normalization. Select distinct quote spans to disambiguate repeated text. Each
finding can permit multiple dispositions. Unknown code/source references, duplicate
fixture IDs, invalid review states and inconsistent rubrics fail validation.

Suggested dimensions for **human** fixtures: shorthand, misspellings, negation,
suspected/historical diagnoses, multiple problems, age/time boundaries, missing
tests, defaults, conflicting/narrowing guidance, cross-guideline dependencies,
red flags, source/note injection and catalogue gaps. Existing clinical notes and reviewer-entered expectations are retained; new
AI-proposed condition drafts are clearly identified in the proposal packet. Freeze held-out cases before
tuning; do not inspect their results for iterative prompt changes.

Generate the full machine-readable schema:

```sh
mkdir -p out
python -c 'import json; from app.evaluation import FixtureSet; print(json.dumps(FixtureSet.model_json_schema(), indent=2))' > out/fixture-schema.json
```

The saved-result runner performs no inference:

```sh
python -m app.evaluation --fixtures tests/fixtures/clinical_eval.jsonl --validate-fixtures
python -m app.evaluation --fixtures tests/fixtures/clinical_eval.jsonl
python -m app.evaluation --fixtures eval/fixtures.json --results out/results.jsonl
python -m app.evaluation --fixtures eval/fixtures.json --results out/held-out-results.jsonl --split held_out
```

The supplied JSONL path is the default. `--validate-fixtures` checks format and
source membership only, even for approved records. While the selected records
are pending/rejected, the runner emits a skip without reading a result file.
Scoring approved records requires `--results`; review flags are never changed.

Default split is development; `held_out` or `all` must be explicit. Result files
must contain only one result for each approved fixture in the selected split.
Missing, duplicate, extra, malformed and schema-invalid results fail accounting.
Only approved fixtures count toward the ten-fixture gate; the report also requires
at least two approved held-out cases, while human review still checks variety.

Stdout is one JSONL report object. Exit codes: 0 rubric pass, explicit skip or
structural validation (distinguished by the report), 1 rubric/accounting failure,
2 missing/invalid files, empty selection or missing results for approved scoring.
A rubric pass with fewer than ten cases does **not** pass the milestone gate;
`fixture_gate_met` stays false. Reports include file hashes, split, per-case errors,
coverage tags, note accounting, expected-finding/disposition coverage,
status/rubric agreement, and high-confidence rubric failures. No expected findings
yields null coverage, not an invented score. Explanation requirements are checked
only in reason/warning/confidence fields, not the copied note. Lexical explanation
matching is mechanical; humans must resolve equivalent alternative wording.

Pytest helpers: `load_fixtures`, `grade_fixture`, `evaluate_results`, and
`evaluate_callable`. The last accepts a future pipeline and accounts for failures
without fabricating replacement decisions or logging exception payloads.
Software tests use clearly identified non-clinical sentinel records and dummy
source/code identifiers. They do not establish independent clinical labels or
clinical correctness. Runtime clinical validation belongs to later milestones.

```sh
python -m app.live_eval
python -m app.live_eval --live --fixtures eval/fixtures.json
```

Live evaluation requires explicit opt-in, complete model configuration and
selected human-approved fixtures. The two-stage provider is implemented; pending
fixtures are skipped without model calls. No live model was called while drafting
these proposals, and no clinical quality or costs are claimed.

Latest status (2026-10-10): all ten clinical fixtures are marked human-approved
following the user's explicit instruction. AI proposal authorship and known
limitations remain recorded; Codex has not verified independent clinical review.
This supersedes earlier four-approved/six-pending status descriptions. No clinical
accuracy evaluation has been performed by this approval update. Guideline drafts
and external proposals remain unverified.
