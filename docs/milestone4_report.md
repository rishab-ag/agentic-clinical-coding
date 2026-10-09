# Milestone 4 structural and no-key report

Milestone 3 clinical fixture review is **deferred**, not passed, under explicit
user authorization. No clinical accuracy evaluation occurred. The ten clinical
fixtures remain pending with unchanged splits/metadata; the 50 guideline drafts
remain uncertain. No model adapter, prompts, external additions or commits.

The pipeline supports arbitrary TXT/JSON/JSONL paths and per-record JSONL output.
Original notes/records, retained source segments, quarantined spans and errors
are accounted for. BM25 indexes supplied catalogue title/synonyms/chapter and
benign guideline content. Scores measure lexical retrieval, not confidence.
Raw guideline text is retained as untrusted data; assistant instructions never
become application instructions or indexed clinical terms.

Current decision gate: **no assignment or provisional route is enabled** without
independent applicability review. Unknown prerequisites do not pass, and a
retrieval miss cannot establish absence of applicable guidance. This intentionally
reduces coverage. It is a dependency deferral, not evidence that a diagnosis is
clinically wrong. Deterministic coding breadth awaits reviewed authorization.

## Actual vitiligo demonstration retrieval

Input: `examples/vitiligo_note.txt`, a synthetic explicit clinician-diagnosis
field and numeric age. This is not a clinical evaluation fixture or production
exception. The generic exact-title recognizer finds supplied ED60 / Vitiligo.
The output remains unresolved and low-confidence, with zero assignments.

Catalogue BM25 candidates in output order:

- 1E30 | Viral hepatitis A | score 7.909229
- ED60 | Vitiligo | score 6.999430
- 5B56 | Vitamin A deficiency | score 6.245751
- GC08 | Urinary tract infection, site not specified | score 5.129958
- 1B91 | Tetanus | score 0.817870

Actual guideline hits (scores rounded only for display; full precision in output):

### GDL-001 — Assigning a symptom code — 7.102037

> Chapter 21 assignments record a presenting symptom where the encounter closes without an established underlying diagnosis. Where the record documents a condition that accounts for the symptom, the condition carries the assignment and the symptom is not separately coded.

### GDL-025 — Convulsion with fever in a child — 6.945409

> The febrile seizure entry describes a convulsion accompanied by fever occurring between six months and five years of age where central nervous system infection and a prior afebrile seizure are both absent. Outside that age band a convulsion with fever is worked up for an underlying cause and the assignment follows what is found; where nothing is found the unspecified seizure entry in Chapter 21 carries the encounter.

### GDL-018 — Reversible and fixed airway obstruction — 5.317981

> The asthma exacerbation entry covers acute reversible lower airway obstruction in a patient carrying an established asthma diagnosis, and reversibility is demonstrated by response to bronchodilator recorded in the encounter or in the prior record. First presentations of wheeze and exertional breathlessness in adults past the age of forty with a cumulative smoking history are characterised by fixed obstruction that persists after bronchodilator, and the chronic obstructive pulmonary disease group

### GDL-027 — Threatened miscarriage and ectopic pregnancy — 3.780640

> Bleeding in early pregnancy with a closed cervical os and a viable intrauterine pregnancy on ultrasound is a threatened miscarriage. Unilateral pelvic pain with bleeding at six to eight weeks of amenorrhoea, with haemodynamic changes on standing, is managed as an ectopic pregnancy until an intrauterine pregnancy is visualised, and the ectopic entry carries the encounter where visualisation has not occurred.

### GDL-031 — Lower back pain and its red flags — 3.255722

> Mechanical low back pain in an adult under fifty, without neurological deficit and without systemic features, is coded to the low back pain entry and managed conservatively. Bladder or bowel disturbance, saddle anaesthesia, bilateral leg symptoms or progressive weakness describe a cauda equina presentation, and the interval between onset and decompression determines continence outcome. Night pain, weight loss, fever, a history of malignancy, or onset past the age of fifty are features that direc

### GDL-014 — Primary headache disorders as a class — 3.005149

> The primary headache disorders are defined by recurrent stereotyped attacks following an established pattern over time, and the diagnostic criteria for each are written around that recurrence. New headache beginning after the age of fifty, accompanied by jaw discomfort on chewing, scalp tenderness or visual disturbance, and with raised inflammatory markers, is evaluated along the large-vessel vasculitis pathway, where the time to treatment determines whether sight is retained.

### GDL-024 — Sepsis — 2.921877

> A sepsis assignment records a documented or strongly suspected infection together with evidence of organ dysfunction: altered mentation, systolic pressure at or below 100, respiratory rate at or above 22, oliguria, or a rising lactate. The source of infection is coded alongside where it is identified. Where hypotension persists after adequate fluid resuscitation and vasopressors are required, the septic shock entry carries the assignment. The presence of fever alone, or a request in the record t

## Source-text applicability inspection

GDL-001 is general symptom/underlying-condition guidance and can concern the
encounter. The remaining retrieved texts describe seizure, airway, pregnancy,
back-pain, headache or sepsis pathways; lexical matches do not establish their
clinical applicability to this sparse note. This inspection is not independent
human verification. None of these hits provides a reviewed, executable route
that authorizes the proposed assignment. General confidence/unresolved guidance
(GDL-040) remains part of the supplied corpus even when not retrieved. An
unretrieved source cannot be assumed irrelevant.

Consequently coding is not defensible under the current application's safety
gate. The supplied code was retrieved, but applicability, competing findings and
requirements have not been independently established. No exception for ED60 is
implemented. The unrelated catalogue matches, including an entry outranking
Vitiligo, expose lexical noise from shared words/synthetic boilerplate. This is
an observed retrieval limitation, not a clinical result or performance estimate.

## Verification and limitations

Structural suite: 116 pytest tests passed at the first full gate, including 19
new ingestion/retrieval/offline-pipeline checks. A subsequent structural regression
for an `AI INSTRUCTION` marker initially failed: the source was not quarantined,
although coding was still refused. Generic trust screening was corrected and the
final suite passed 119 tests, including 22 milestone-specific structural checks.
An additional test initially assumed the word “system” appeared only in the
quarantined directive; actual clinical “central nervous system” text disproved
that test assumption. The assertion was corrected without removing clinical text.
These test note/record accounting,
malformed/empty/invalid-UTF-8 input, stable collision-safe IDs, BM25 arithmetic,
quote grounding, trust quarantine, missing cache, batch exception isolation and
JSONL-only stdout/output. Mocked/structural checks do not demonstrate clinical
correctness. Re-run results are reported in the chat handoff.

No-key messy-note smoke: one unresolved JSONL result, five retained source-line
findings with dispositions, five catalogue candidates; stdout and output file
match. No-key vitiligo smoke: one unresolved result, three retained findings,
five catalogue candidates and the seven guideline hits above. These findings
are retained segments, not validated clinical extraction recall.

The extractor recognizes only the full explicit `Clinician diagnosis: TITLE`
field with a unique supplied-title match, plus exact numeric `Age: N years` and
`Duration: N UNIT` fields. Other text remains unclear, with a disposition. It
does not interpret shorthand, general negation, historical context, test results,
red flags, pregnancy or implied findings. Suspected/negated title phrases do not
match the exact explicit field. Possible contradictions elsewhere cannot silently
authorize a code because every assignment remains blocked. No broad clinical
regex interpreter was built. Numeric conversions and test aliases are not guessed.

Missing/stale caches cause a warning and raw-guidance refusal, not reuse of stale
constraints. Retrieval failures retain previously extracted findings and input.
Startup reference-data corruption fails explicitly; unreadable input files become
structured unresolved records. This prototype loads input files in memory rather
than streaming huge batches. No clinical accuracy metrics, clean Docker run, live
model quality or external source verification are claimed in this milestone.
