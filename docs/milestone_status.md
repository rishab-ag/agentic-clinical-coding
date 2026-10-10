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

Latest fixture status: four records retain reviewer-entered approval; six
incomplete prose expectation sets were returned to pending with user permission.
Fixture schema validation passes; `fixture_gate_met` remains false. Clinical
labels, splits, reviewer identifiers and timestamps were preserved. This supersedes
earlier descriptions that all ten records were marked approved. No new clinical
scoring or independent source verification was performed.

Six pending fixture condition sets now have AI-proposed executable checks.
Schema/path validation is clean; review ambiguities are documented in
`fixture_expectation_proposals.md`. Four reviewer approvals and six pending
states remain unchanged. No clinical scoring or new independent approval occurred.

Latest status (2026-10-10): all ten clinical fixtures are marked human-approved
following the user's explicit instruction. AI proposal authorship and known
limitations remain recorded; Codex has not verified independent clinical review.
This supersedes earlier four-approved/six-pending status descriptions. No clinical
accuracy evaluation has been performed by this approval update. Guideline drafts
and external proposals remain unverified.

No-key fixture evaluation executed on 2026-10-10: development 5/7 rubric matches,
held-out 2/3, all ten records accounted for and unresolved. Both scoring runs
returned exit 1; clinical evaluation has not passed. Live model evaluation skipped
because credentials/configuration are absent. See `clinical_testing_report.md`.

Live Gemini status (2026-10-10): the earlier HTTP 404 was a retired model ID
(`gemini-2.5-flash`), not an adapter fault. With current model IDs both stages
complete. Prompt `two-stage-v3` states the output accounting contract; omitted
guideline reviews are handled locally without relaxing assignment gates. Single
live runs: two fixtures coded, eight refused, held-out 2/3 rubric matches with
E09 refused. Compose now forwards optional model variables. Suite: 220 passed,
1 skipped. See `clinical_testing_report.md` and `gemini.md`. Free-tier quota
limited every run; no clinical accuracy claim is made.
