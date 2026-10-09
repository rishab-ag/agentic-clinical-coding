"""Conservative instruction-span screening. All source content stays untrusted.

This detects obvious directives, not every possible injection. No detector miss
grants authority to source text; downstream prompts/validators must enforce that.
"""
import re
from typing import List

from pydantic import Field

from app.models import Contract


class TextSegment(Contract):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    disposition: str
    reason: str


class TrustScan(Contract):
    segments: List[TextSegment]
    warnings: List[str]
    reliability: str

    @property
    def retained_text(self):
        # Keep boundaries; never join surviving pieces into a new clinical claim.
        return "\n".join(s.text for s in self.segments if s.disposition == "retained")


_DIRECTIVE = re.compile(
    r"\b(?:assistant|chatgpt|language model|processing agent)\b|"
    r"\b(?:system|developer|ai)\s+(?:directive|message|instruction|override)\b|"
    r"\b(?:ignore|disregard|override)\b[^.!?\n]{0,100}\b(?:instructions|guidance|rules|system|prompt)\b|"
    r"\b(?:omit|hide|suppress|remove)\b[^.!?\n]{0,80}\b(?:evidence|warnings|output|citations)\b|"
    r"\b(?:return|output|assign)\s+(?:the\s+)?code\b[^.!?\n]{0,80}\b(?:confidence|regardless)\b",
    re.IGNORECASE,
)


def scan_untrusted_text(text: str) -> TrustScan:
    """Screen bracketed annotations, sentences and lines without interpreting medicine."""
    # Brackets containing a directive are kept together, including nested brackets.
    brackets = []
    stack = []
    for index, char in enumerate(text):
        if char == "[":
            stack.append(index)
        elif char == "]" and stack:
            start = stack.pop()
            if not stack:
                brackets.append((start, index + 1))
    ranges = [(a, b) for a, b in brackets if _DIRECTIVE.search(text[a:b])]
    # A malformed annotation with a directive has uncertain segmentation.
    uncertain = any(_DIRECTIVE.search(text[a:]) for a in stack)
    if uncertain:
        ranges.extend((a, len(text)) for a in stack if _DIRECTIVE.search(text[a:]))
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|\n|$)", text):
        if not _DIRECTIVE.search(match.group()):
            continue
        if any(a <= match.start() < b or match.start() <= a < match.end() for a, b in ranges):
            # Already isolated annotation; leave the clinical sentence outside it.
            outside = match.group()
            for a, b in ranges:
                left, right = max(a, match.start()), min(b, match.end())
                if left < right:
                    outside = outside[:left - match.start()] + " " * (right - left) + outside[right - match.start():]
            if not _DIRECTIVE.search(outside):
                continue
        ranges.append((match.start(), match.end()))
    merged = []
    for a, b in sorted(ranges):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    segments = []
    cursor = 0
    for a, b in merged:
        if cursor < a:
            segments.append(TextSegment(start=cursor, end=a, text=text[cursor:a], disposition="retained", reason="Untrusted source data"))
        segments.append(TextSegment(start=a, end=b, text=text[a:b], disposition="quarantined", reason="Possible assistant-directed instruction or behavior override"))
        cursor = b
    if cursor < len(text):
        segments.append(TextSegment(start=cursor, end=len(text), text=text[cursor:], disposition="retained", reason="Untrusted source data"))
    warnings = [f"trust_warning: quarantined source offsets {a}:{b}" for a, b in merged]
    if uncertain:
        warnings.append("trust_warning: annotation boundary uncertain; source cannot authorize high confidence")
    return TrustScan(segments=segments, warnings=warnings,
                     reliability="uncertain" if merged else "untrusted")
