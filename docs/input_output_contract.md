# Input and output contract

Milestone 4 implements `--input PATH` and `--output PATH`. The offline pipeline
retrieves context and explicitly refuses assignments while authorization cannot
be established; clinical accuracy scoring remains deferred.

UTF-8 input formats:

- `.txt`: the entire file is one note, including newlines and empty text.
- `.json`: one object or an array of objects, each with `note_id` (nonempty
  string) and `text` (string). No guessing alternative field names.
- `.jsonl`: one such object per physical line. Blank/malformed lines are
  records that receive explicit unresolved errors, not silently skipped.

Preserve order and supplied IDs. Missing or duplicate IDs receive a stable
record-position identifier and a warning; retain the original record under
`original_record`. Generated IDs avoid collisions with every supplied valid ID.
Invalid JSON documents receive a file-level unresolved result. An empty TXT,
JSONL file or JSON array produces one explicit empty-input result. Every recognized
record produces exactly one result, including empty or malformed records.
JSONL invalid UTF-8 is isolated per line; original bytes are base64-preserved.
Duplicate JSON keys, nonstandard constants and unpaired Unicode surrogates are
rejected and the raw input retained. Extra object fields are retained as data.

Stdout and `--output` contain identical JSONL: one CodingResult JSON object
per line, including a single TXT note. Operational logs go to stderr. Original
note text is retained. The bootstrap `--self-check` already emits this format,
but is a synthetic wiring check, not a clinical test. Output paths cannot overwrite
the input, supplied reference files, guideline cache, or human-owned clinical
fixture/review files. Create output directories before using `--output`.

Models reject extra fields and separate differential hypotheses from findings.
Each finding requires a disposition and reason. Assignments accept supplied
origin only; status must agree with per-assignment certainty. Numeric retrieval
scores are separate from categorical confidence. Evidence carries exact quotes
and optional paired offsets. Corpus membership, original-note quote grounding,
clinical applicability, and full guideline permission validation arrive in later
milestones; schema validity alone does not establish clinical correctness.
`retrieved_evidence` cites actual catalogue/guideline context and lexical scores.
`guideline_checks` exposes source IDs, review states and three-valued checks;
uncertain records stay unknown. Quarantined note spans remain separate evidence,
while benign retained segments receive findings with explicit dispositions.
Segments are not a claim of complete clinical finding extraction.
