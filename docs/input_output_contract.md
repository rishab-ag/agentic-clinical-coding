# Input and output contract

Milestone 1 defines contracts only. File ingestion, `--input PATH` and
`--output PATH` belong to Milestone 4; no clinical decisions occur yet.

Planned UTF-8 input formats:

- `.txt`: the entire file is one note, including newlines and empty text.
- `.json`: one object or an array of objects, each with `note_id` (nonempty
  string) and `text` (string). No guessing alternative field names.
- `.jsonl`: one such object per physical line. Blank/malformed lines are
  records that receive explicit unresolved errors, not silently skipped.

Preserve order and supplied IDs. Missing or duplicate IDs receive a stable
record-position identifier and a warning; retain the original record. Invalid
JSON documents receive a file-level unresolved error. These are planned
ingestion policies, not implemented behavior. Every recognized record must
produce exactly one result, including empty or malformed records.

Stdout and `--output` will contain JSONL only: one CodingResult JSON object
per line, including a single TXT note. Operational logs go to stderr. Original
note text is retained. The bootstrap `--self-check` already emits this format,
but is a synthetic wiring check, not a note-file processor or clinical test.

Models reject extra fields and separate differential hypotheses from findings.
Each finding requires a disposition and reason. Assignments accept supplied
origin only; status must agree with per-assignment certainty. Numeric retrieval
scores are separate from categorical confidence. Evidence carries exact quotes
and optional paired offsets. Corpus membership, original-note quote grounding,
clinical applicability, and guideline permission validation arrive in later
milestones; schema validity alone does not establish clinical correctness.
