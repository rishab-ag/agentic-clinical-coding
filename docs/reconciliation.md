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
