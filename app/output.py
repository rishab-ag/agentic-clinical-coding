"""Compact per-note view of a CodingResult: what the brief asks for, nothing else.

The complete audit record (hashes, offsets, raw guideline text, original record) stays
available through `--full`; this view only drops fields, it never rewrites a value.
"""


def compact(result, titles):
    """`titles` maps supplied catalogue code to title; assignments are supplied-origin only."""
    provenance = result.provenance
    return dict(
        note_id=result.note_id,
        status=result.status,
        mode=provenance.mode,
        model=provenance.model,
        assignments=[dict(
            code=a.code,
            title=titles.get(a.code),
            certainty=a.certainty,
            confidence=a.confidence.level,
            note_evidence=[e.source_quote for e in a.evidence if e.source_type == "note"],
            guideline_ids=a.guideline_ids,
        ) for a in result.assignments],
        confidence=dict(level=result.confidence.level,
                        increase_if=result.confidence.increase_if,
                        decrease_if=result.confidence.decrease_if),
        unresolved=result.unresolved,
        findings=[dict(
            quote=f.evidence.source_quote.strip(),
            assertion=f.assertion,
            disposition=f.disposition,
            assignment_code=f.assignment_code,
            reason=f.reason,
        ) for f in result.findings],
        candidates_considered=[dict(
            code=c.code,
            title=c.title,
            origin=c.catalogue_origin,
            status=c.status,
            reason=c.reason,
            missing_discriminators=c.missing_discriminators,
            # Expanded-only codes must always carry their external source.
            **(dict(source=c.source) if c.catalogue_origin == "expanded" else {}),
        ) for c in result.candidates_considered],
        guidelines_retrieved=[dict(id=r.source_id, title=r.title, quote=r.source_quote)
                              for r in result.retrieved_evidence if r.source_type == "guideline"],
        safety_flags=result.safety_flags,
        warnings=result.warnings,
    )
