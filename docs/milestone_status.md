# Milestone review status

- Milestones 1–3 engineering infrastructure implemented; human review remains required.
- Milestone 3 clinical fixture approval gate: **deferred**, explicitly authorized
  by the user on 2026-10-10 as a temporary dependency deferral. It has not passed.
  All ten fixtures now carry reviewer-entered approval metadata, but six prose
  condition sets still prevent validation. Splits and clinical labels are preserved;
  clinical scoring remains blocked.
- Milestone 2 semantic review: all 50 guideline drafts remain uncertain and
  unverified. No independent applicability approval is inferred.
- Milestone 4: ingestion, BM25 retrieval and conservative no-key processing.
  All decisions abstain while safe authorization cannot be established.
- Milestone 5: authorized optional two-stage model adapter and grounding checks.
  No-key processing remains available. Live inference/clinical quality remain
  untested without credentials and independently approved fixtures.
- Milestone 6: authorized reconciliation and evidence validation implemented,
  with one conservative decision-output repair. Structural checks do not satisfy
  the deferred clinical gate. See `docs/reconciliation.md`.

Outstanding: independent fixture approval, explicit executable expectations for
ambiguous prose, human guideline interpretation review, and clinical evaluation.
Software checks and smoke tests are not evidence of clinical accuracy.

Milestone 7 infrastructure and primary-source review packet implemented. External
source/permission approval remains outstanding; both proposals are pending and
excluded from runtime retrieval. The external expansion gate has not passed.
Milestone 8 packaging implemented; see runtime verification below.

Milestone 8: container packaging, pinned requirements, concise README and local
reproducibility checks implemented. Docker execution is unvalidated because the
Docker executable is unavailable. The final reproducibility gate is not passed.
Fresh exported-tree installation and no-key processing passed; this is not a
Docker or committed clean-clone verification. Prior review gates remain open.

Latest end-to-end verification (2026-10-10): Docker build and default startup
passed; the mounted two-record batch and ten synthetic fixture notes each emitted
schema-valid JSONL with preserved note text. The suite passed 181 tests with one
opt-in live test skipped. This supersedes earlier Docker-unavailable limitations.
Clinical evaluation remains blocked by unresolved prose expectations; no clinical
accuracy result or independent source approval is claimed.
