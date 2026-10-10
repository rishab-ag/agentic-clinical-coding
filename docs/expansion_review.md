# Milestone 7 external source review packet

Access date: 2026-10-10. **Current state:** `1B71` is active after an AI-performed
source check requested by the repository owner; the skin-referral excerpt remains
`pending_human_review` and out of retrieval. No entry has independent human or
clinical approval; see "Source check and activation" below. Source observations
are fetched facts, not confirmed clinical labels.

## Gaps observed in supplied data

- GDL-014 describes a large-vessel vasculitis pathway. No catalogue title names
  giant cell arteritis. No current WHO classification entity was fetched for this
  gap; no code proposal is recorded for it.
- GDL-015 distinguishes clustered transient events from resolved single events.
  The catalogue includes transient ischaemic attack and a stroke title; no distinct
  recurrent-event syndrome was found by title inspection. A dedicated ICD entry
  is not assumed. The supplied stroke code also needs source review (below).
- GDL-028 distinguishes chronic hypertension carried into pregnancy. Catalogue
  titles include essential/secondary hypertension and gestational hypertension,
  but no chronic-hypertension-in-pregnancy title was found. Missing exact mappings
  must not be inferred from this title search.
- GDL-032 describes necrotising infection; no necrotising fasciitis title occurs in
  the supplied catalogue. This is the source-supported proposal investigated here.

These are corpus-audit observations, not runtime disease-to-code branches. Clinical
fixture labels, held-out records and the 50 uncertain drafts were not used to tune
retrieval or modified.

## Proposed additions for independent review

| Code | Title | Primary-source URL | Fetched facts | Not independently verified |
| --- | --- | --- | --- | --- |
| 1B71 | Necrotising fasciitis | [WHO Reference Guide](https://icdcdn.who.int/icd11referenceguide/en/refguide.pdf#page=342) | The fetched PDF displays this exact pair on PDF page 342; copyright page says 2022. | Current release-specific mapping, WHO entity URI, chapter/hierarchy, software reuse approval and human source review. |
| — | WHO skin disease classification: urgent referral excerpt | [WHO skin classification](https://cdn.who.int/media/docs/default-source/ntds/skin-ntds/common-skin-diseases-for-managemen-or-referral-at-primary-health-care-level.pdf#page=12) | PDF page 12 includes disproportionate pain and hospital/surgical referral in the necrotising-fasciitis row. | Effective/publication date, reuse permission, human source review and clinical applicability. |

The stored fragment hash protects the **recorded fragment**, not the remotely
served PDF bytes or accuracy of transcription. This distinction is intentional;
no downloaded-file hash is claimed. The fragments are short review quotations,
not a redistributed classification or a complete clinical guideline. The skin
excerpt alone cannot authorize diagnosis or assignment.

The fetched [WHO digital licence](https://icd.who.int/en/docs/ICD11-license.pdf)
requires code, title and URI for software incorporation (section 1.2.3) and
attribution. The proposed entry has no fetched WHO entity URI, so software reuse
is not marked approved. No skin-document licence was located in the fetched text.
A release-specific WHO browser entity request failed. NICE's recommendations
appeared in search, but direct page/licence requests failed; no NICE content was
added. URLs and snippets alone do not satisfy the source review gate.

## Supplied-vs-source audit; supplied files remain authoritative and unchanged

| Supplied entry | Fetched WHO observation | Assessment |
| --- | --- | --- |
| CA22: pneumonia without identified organism | Reference Guide PDF pages 136–137 associates CA22 with COPD; page 136 associates CA40.Z with organism-unspecified pneumonia. | Documented conflict with fetched guide, not certified against current MMS. |
| CA40: COPD | Reference Guide PDF page 137 associates CA40 with pneumonia. | Documented conflict with fetched guide; no rewrite or collision override. |
| MD11: chest pain; MD11.2: dyspnoea | Guide PDF page 226 shows MD11.1 for asphyxia. | Suspicious family, but parent/MD11.2 mapping not established. |
| MD30: haemoptysis | No MD30 occurrence found in the fetched guide; WHO-domain search yielded no result. | Unverified; absence from a reference guide proves no mismatch. |
| 8B00: cerebral ischaemic stroke | Guide PDF page 341 uses 8B00 for intracerebral haemorrhage and 8B11 for cerebral ischaemic stroke. | Documented conflict with fetched guide, not current-release certification. |
| CA23 / CA23.1; GA30 / GA30.1; NE60 / NE60.1 | Supplied titles pair bacterial pneumonia/lung abscess, epididymo-orchitis/ovarian cyst, concussion/drowning respectively. | Hierarchical-looking IDs are not proof of medical parentage; exact WHO mappings were not fetched. |

All guide observations above come from the [same fetched WHO reference guide](https://icdcdn.who.int/icd11referenceguide/en/refguide.pdf).
No current-version mismatches, licence permissions or hierarchical equivalences
are asserted beyond those limited observations.

## Infrastructure and review procedure

`data/expanded/proposals.json` is separate from supplied data. `app/expansion.py`
validates source URLs, fragment hashes, exact code/title presence, excerpt
containment, IDs, supplied linkages, collision prevention and approval digests.
A pending or rejected record never enters retrieval. A human approval requires
source, exact mapping and reuse checks, reviewer/time, and a digest binding the
review to the unchanged proposal. This metadata cannot authenticate the reviewer;
the human-controlled repository is the trust boundary.

After independent source review, record complete source facts, version, chapter,
WHO entity URI and reuse evidence. Compute `entry_digest(ExternalEntry)` after
those edits and before recording `review`; the reviewer owns approval. Codex has
not approved or filled missing source facts. Review of the source is separate
from clinical applicability or evaluation label approval.

Only source-reviewed external codes can enter the separate BM25 index. They remain
unresolved candidates with original source URL and expanded origin; assignments
remain supplied-only. All source-reviewed external guideline excerpts go to Stage
2 and require explicit applicability review, alongside all 45 supplied snippets.
Missing or unknown external review blocks assignments. Invalid expansion data is
excluded with a warning; it cannot replace supplied entries. No runtime network
fetch is introduced. JSONL output cannot overwrite the expansion directory.

Stop for independent review here. Milestone 8 has not been implemented. Milestone 3
clinical approval remains deferred; clinical accuracy is unscored.

## Source check and activation (2026-10-10)

Performed by Claude Code at the repository owner's instruction, by downloading the
files and extracting their text. This is an AI source check, not an independent
human review. The manifest status value `human_approved` is the activation state
the loader requires; the `review.reviewer` field records who actually checked.

| Code | Title | Primary-source URL | Verified facts | Unverified facts |
| --- | --- | --- | --- | --- |
| 1B71 | Necrotising fasciitis | [WHO Reference Guide](https://icdcdn.who.int/icd11referenceguide/en/refguide.pdf#page=342); [ICD-11 MMS 2026-01 release table](https://icdcdn.who.int/static/releasefiles/2026-01/SimpleTabulation-ICD-11-MMS-en.zip) | Guide PDF page 342 shows the exact pair. The release table lists code 1B71, this title, Foundation URI `http://id.who.int/icd/entity/522973276`, chapter 01 "Certain infectious or parasitic diseases", parent block "Pyogenic bacterial infections of the skin or subcutaneous tissues". The [WHO licence](https://icd.who.int/en/docs/ICD11-license.pdf) sections 1.2.2-1.2.3 allow software incorporation with code, title and URI under CC BY-ND 3.0 IGO. | Independent human or clinical review; the WHO browser page itself; applicability to any note. |
| — | WHO skin disease classification: urgent referral excerpt | [WHO skin classification](https://cdn.who.int/media/docs/default-source/ntds/skin-ntds/common-skin-diseases-for-managemen-or-referral-at-primary-health-care-level.pdf#page=12) | PDF page 12 contains the quoted sentence in the necrotising-fasciitis urgent-referral row. The cover reads "Version 1.0" and "For external expert review draft". | Final publication status; reuse terms (none found in the 45-page PDF); clinical applicability. **Not activated.** |

Downloaded-file SHA-256 values are recorded in the manifest's `fetched_facts`.
Expanded entries are now ranked in one index with the supplied catalogue and
matched on title and synonyms only; before that change a one-entry index
surfaced 1B71 on an unrelated note through a shared common word. A synthetic
necrotising-fasciitis note returns `unresolved` with 1B71 as an expanded
candidate, offline and through the live model path; no assignment is produced.
