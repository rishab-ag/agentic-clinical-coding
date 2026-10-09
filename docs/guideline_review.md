# Milestone 2: offline guideline normalization and review

The committed cache contains manually seeded semantic drafts for all 45 supplied
snippets, plus five narrower age/time branch drafts. **None is verified.** These
are interpretations for review, not clinical evaluation labels or medical
authority. Overview records are deliberately partial and advisory: they retain
alternative pathways without collapsing them into one executable rule. Raw
guideline text remains authoritative within this supplied corpus.

No clinical restriction regex or model call is used. Numeric operators compare
structured facts; they do not infer medical meaning from prose. No API key or
network is required to validate/load this cache. Additional offline model drafts
can be exported into the same schema using separately supplied credentials; a
model extractor/provider is not implemented in this milestone. Model-produced
records must remain uncertain until independently reviewed.

```sh
python -m app.guidelines
mkdir -p out
python -m app.guidelines --review-report > out/guideline-review.jsonl
python -m app.guidelines --cache PATH_TO_EDITED_CACHE
```

The report emits 45 JSONL objects, each with the original source metadata/text,
trust segmentation, every draft for that source, and its review-payload hash.
Diagnostics/counts go to stderr. Inspect the JSON in an editor. There is no
automatic approval command; validation success never implies clinical approval.

For each record, a human must:

1. Compare each exact quote and character offset to the original snippet.
2. Check applicability, alternatives, AND/OR grouping, exclusions, unit meaning,
   test name/results, age/time boundary inclusion and relationship direction.
3. Correct the draft, split branches or leave ambiguous fields advisory. Add
   missing constraints with their own exact source spans. Empty groups mean
   unknown, never permission or proof of no restrictions.
4. Keep `coverage: partial` until genuinely complete for the quoted branch.
   `reviewed_complete` is a human attestation, never an automated inference.
5. Leave unresolved records `uncertain`, or mark mistaken interpretations
   `rejected`. To verify a corrected record, set its status (and any independently
   reviewed relation status), rerun the report to get the final payload hash,
   then add `review` with `reviewer`, `reviewed_at` (actual ISO timestamp), `note`
   describing the checks, and `payload_sha256`. Because verified status requires
   review metadata, get the payload hash while the record is uncertain; for
   verified relation edits, use `payload_sha256` from `app.constraints` on the
   edited record payload before validation. See the simpler procedure below.
6. Revalidate and run pytest. Codex must not perform this approval on your behalf.

Simplest editing procedure: keep the record uncertain and all relations uncertain,
correct its content, run the report, copy its hash into a human review record,
then change only the record status to verified. Relation approval can be a
separate edit with a new payload hash and independent review. The hash covers
every interpretation field, including relation statuses and coverage; only the
record's own status and review metadata are excluded. To calculate a hash for a
final edited JSON dictionary without prematurely approving it:

```python
import hashlib, json
payload = {k: v for k, v in record.items()
           if k not in ("verification_status", "review")}
digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8")).hexdigest()
```

Use the complete normalized record from the report, which includes defaults.
This digest detects edits after review; it does not authenticate a human or
prove correctness. Review remains an explicit human responsibility. Original
guideline-file byte hash and each snippet's UTF-8 text hash must still match;
quotes/offsets, record uniqueness and relation target membership are checked.
Stale, malformed or unanchored caches fail clearly. Runtime consumers must fall
back to raw guidance or abstain; they must not silently reuse stale annotations.

Only independently verified age/time/test prerequisites may become deterministic
hard checks. The group evaluator returns `met`, `not_met`, or `unknown`; unknown
requirements never pass. Uncertain/rejected records evaluate as unknown. A known
fact requires note provenance, compatible units and a quote in the immutable note.
No implicit unit conversions, test aliases or clinical parsing occur. Even a
`met` mechanical condition does not authorize a diagnosis: other advisory scope,
exclusions, source reliability and raw-source meaning still require assessment.

Relationship traversal returns a cycle-safe **advisory** closure, retaining
verification status and quotes. It never applies precedence merely by date and
does not treat an uncertain supersession proposal as an approved override.
Rejected edges/records are excluded. Missing targets fail validation.

Review ambiguities requiring attention:

- GDL-021: >=16 inflammatory branch versus colloquial “first decade”; no universal
  refusal rule for ages 10–15 is inferred.
- GDL-025: six-month/five-year endpoint inclusion and conversion to years need
  independent review; CNS infection and previous afebrile seizure exclusions
  remain clinical prerequisites.
- GDL-026: medication duration is distinct from headache and medication-day
  frequencies; the source requires all of these.
- GDL-028: exact twenty weeks is not resolved by “after” and “before”.
- GDL-007: the perforation/discharge duration referent requires review.
- GDL-016 explicitly replaces the old pathway confirmation standard; whether its
  supersession covers the GDL-045 addendum is a separate proposed relation.
- GDL-023/GDL-036 reference parasitological confirmation; this does not establish
  that malaria-specific tests should be applied to dengue/TB.
- GDL-041 contains a quarantined appended directive. Benign triage and
  allergy-qualified aspirin statements remain untrusted clinical data.

Trust screening applies identically to notes and guidelines without ID branches.
All characters are preserved in retained/quarantined segments with offsets.
Obvious assistant-directed or behavior-changing text is quarantined, not used
as a condition/relationship quote, and produces visible warnings. Ambiguous
annotation boundaries mark reliability uncertain. Pattern screening is
incomplete; absence of a match never makes source instructions authoritative.
Future prompt and evidence validators must enforce the boundary independently.
