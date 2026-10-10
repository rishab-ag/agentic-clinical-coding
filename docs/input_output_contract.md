# Input and output contract

Milestone 4 implements `--input PATH` and `--output PATH`. The offline pipeline
retrieves context and explicitly refuses assignments while authorization cannot
be established; clinical accuracy scoring remains deferred.

UTF-8 input formats:

- `.txt`: one note, including newlines and empty text. If the file contains
  lines made only of three or more `-`, `=`, `*`, `_` or `#`, it is split into
  one note per delimited block, with a warning on each record.
- `.json`: one object, an array of objects or strings, or an object wrapping a
  single array. The preferred fields are `note_id` and `text`.
- `.jsonl` / `.ndjson`: one object or string per physical line. Blank/malformed
  lines are records that receive explicit unresolved errors, not silently skipped.
- `.csv` / `.tsv`: a header row, then one note per row.
- Any other extension: the content decides (JSON, JSONL, otherwise one
  plain-text note), with a warning naming the choice.

When `text` is absent, note text is read from a recognised field name (`note`,
`note_text`, `consult_note`, `content`, `body`, `narrative`, `free_text`), or
failing that from the longest string field. When `note_id` is absent, the ID is
read from the first field whose name ends in `id`. Every such inference is a
warning on the result, and the original record is kept under `original_record`.
A record with no string field at all is an explicit error, never a guess.

Preserve order and supplied IDs. Missing or duplicate IDs receive a stable
record-position identifier and a warning; retain the original record under
`original_record`. Generated IDs avoid collisions with every supplied valid ID.
Invalid JSON documents receive a file-level unresolved result. An empty TXT,
JSONL file or JSON array produces one explicit empty-input result. Every recognized
record produces exactly one result, including empty or malformed records.
JSONL invalid UTF-8 is isolated per line; original bytes are base64-preserved.
Duplicate JSON keys, nonstandard constants and unpaired Unicode surrogates are
rejected and the raw input retained. Extra object fields are retained as data.

By default each line is a compact view with exactly the fields the brief asks
for: `note_id`, `status`, `assignments` (code, title, certainty, confidence,
note quotes, guideline IDs), `confidence` with `increase_if`/`decrease_if`,
`unresolved`, plus `findings` with dispositions, `candidates_considered`,
`guidelines_retrieved`, `safety_flags`, `warnings`, `mode` and `model`. Pass
`--full` for the complete audit record described below (hashes, offsets, raw
guideline text, original record, provenance). The paragraph below describes
the full record.

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
