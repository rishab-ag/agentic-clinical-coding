# Milestone 6 validation and reconciliation

The model path validates every extracted finding's original-note quote, then
requires exactly one nonblank disposition per finding. Assignments link back to
those immutable findings and include matching original-note evidence. Definitive
assignments require a confirmed, current, encounter-relevant patient finding.
Supplied code membership, catalogue origin, guideline IDs, applicable guidance,
requirements, provisional permission and source spans are checked before acceptance.
Case and whitespace alone are normalized; punctuation is preserved. Quarantined
instructions cannot supply evidence. Application warnings survive model failures.

One decision-output repair is permitted for malformed JSON/schema or missing
finding dispositions. The request includes the original complete note/corpus,
extraction, invalid output and sanitized validator errors. The repair adapter
makes exactly one HTTP request, with transport retries disabled. Full context
bounds and actual token usage are recorded, including the repair. Every repaired
assignment must be identical to a schema-valid original assignment; guidelines
cannot change when assignments survive, and confidence cannot increase. Invalid
or unparseable assignments can only be removed. Grounding and clinical restrictions
are revalidated against application-owned originals. Clinical validation failures
are refused directly. Stage 1 failures retain the offline findings and abstain;
there is deliberately no extraction repair that could invent a stronger assertion.

Verified numeric groups retain all/any semantics. Advisory interpretations are
not promoted to deterministic hard gates. Unknown whole-corpus applicability,
unmet prerequisites, verified exclusions and unresolved verified dependencies
block assignments. All 50 current drafts remain unverified. Raw-text clinical
narrowing/conflicts are assessed by Stage 2; local quote validation is necessary
but cannot prove a model's interpretation. Any unresolved finding or safety flag
blocks high-confidence assignments, conservatively including nonmaterial flags.

On failure, each finding remains unresolved with a reason; retrieved candidates,
source/trust warnings and model provenance remain visible. Model-proposed expanded
candidates are retained as unresolved **unverified claims**, with their claimed
source and an explicit warning. There is no verified external expansion loader in
this milestone; implementing and independently reviewing expansion is Milestone 7.
Expanded-origin assignments always fail schema validation.

Validation uses non-clinical dummy records, never authored clinical labels. The
held-out loader preserves E08–E10 and refuses scoring because all ten fixtures are
pending approval. Milestone 3 remains deferred, not passed. Live inference and
clinical accuracy are untested. A review caught that the initial validator checked
each numeric condition separately, losing any-group semantics; this milestone
uses the group evaluator instead. No clinical-correctness claim follows from tests.

A live Gemini response exposed a structural repair classification gap: an
unlinked coded/subsumed disposition raised a generic ValueError, so the permitted
repair never ran. It now raises ReconciliationFailure. One repair may correct
dispositions or refuse, but cannot add/change assignments, linked finding IDs,
quotes, assertions or clinical certainty. Full original-source validation still
runs afterward. Dummy regressions cover preserving an unlinked finding as
unresolved and rejecting repairs that expand assignment links to suspected
findings. No fixture-specific medical rule was introduced.

## Model citation formatting (two-stage-v2)

A repaired live proposal failed because its guideline offsets did not match the
raw guideline body. Both stages now request exact quotes with null start/end,
and the Evidence schema describes offsets as optional, independently computed
source-text character positions. Model-generated prompt/token offsets must not
be used as source offsets. The application does not remove or correct invalid
spans after receipt: explicitly supplied bad spans still fail. Null-offset quotes
are validated against retained original source text with case/whitespace
normalization only; punctuation changes and fabricated text are rejected.

The updated prompt version records this formatting contract. Production medical
rules, assignment evidence, reviewer metadata and fixture expectations are
unchanged. Full regression tests: 215 passed, 1 skipped. No-key messy-note smoke
and diff check passed. A live single-note verification is reported separately.

Live verification with two-stage-v2 reached both stages and one repair. E01 still
failed its rubric, now with `Unresolved finding or safety concern blocks high
confidence`, rather than the earlier guideline-offset error. Actual input tokens:
extract 503, decide 21193, repair 28460. No assignment was accepted; this does not
establish clinical correctness. The confidence guard was not removed or relaxed.
