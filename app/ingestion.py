"""Loss-accounted UTF-8 input records; no clinical interpretation."""
import base64
import json
import math
from pathlib import Path
from typing import Any, List

from pydantic import Field

from app.models import Contract, Note


class InputRecord(Contract):
    note: Note
    position: int = Field(ge=1)
    original_record: Any
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def _constant(value):
    raise ValueError("Non-standard JSON constant")


def _json(text):
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("JSON numeric value cannot be represented safely")
        return result
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key; retain the original record instead of overwriting")
            result[key] = value
        return result
    obj = json.loads(text, parse_constant=_constant, parse_float=finite_float, object_pairs_hook=unique_keys)
    json.dumps(obj, ensure_ascii=False).encode("utf-8")  # Reject unpaired Unicode surrogates.
    return obj


def read_records(path: Path) -> List[InputRecord]:
    """One result per physical JSONL line, JSON element, or TXT/file-error record."""
    try:
        raw = path.read_bytes()
    except OSError:
        return [InputRecord(note=Note(note_id="record-000001", text=""), position=1,
                            original_record={"input_path": str(path)}, errors=["Input file cannot be read"])]
    extension = path.suffix.casefold()
    parts = raw.splitlines(keepends=True) if extension == ".jsonl" else [raw]
    if not parts:
        parts = [b""]
    parsed = []
    for part in parts:
        errors = []
        try:
            text = part.decode("utf-8")
        except UnicodeDecodeError:
            parsed.append((None, part.decode("utf-8", errors="replace"),
                           {"raw_bytes_base64": base64.b64encode(part).decode("ascii")}, ["Input record is not valid UTF-8"]))
            continue
        if extension == ".txt":
            parsed.append((None, text, text, []))
            continue
        if extension not in (".json", ".jsonl"):
            parsed.append((None, text, text, ["Unsupported input extension; use TXT, JSON or JSONL"]))
            continue
        try:
            obj = _json(text)
        except ValueError:
            parsed.append((None, text, text, ["Malformed or empty JSON record/document"]))
            continue
        objects = obj if extension == ".json" and isinstance(obj, list) else [obj]
        if not objects:
            parsed.append((None, "", obj, ["Empty JSON array: no note records supplied"]))
        for item in objects:
            if not isinstance(item, dict):
                parsed.append((None, json.dumps(item, ensure_ascii=False), item, ["Note record must be an object with text"]))
                continue
            value = item.get("text")
            errors = [] if isinstance(value, str) else ["Note record text must be a string"]
            parsed.append((item.get("note_id"), value if isinstance(value, str) else json.dumps(item, ensure_ascii=False), item, errors))
    reserved = {identifier for identifier, _, _, _ in parsed if isinstance(identifier, str) and identifier.strip()}
    used = set()
    records = []
    for position, (identifier, text, original, errors) in enumerate(parsed, 1):
        warnings = []
        if not isinstance(identifier, str) or not identifier.strip() or identifier in used:
            if extension != ".txt":
                warnings.append("Missing/invalid/duplicate ID replaced; original record retained")
            identifier = f"record-{position:06d}"
            while identifier in reserved or identifier in used:
                identifier += "-generated"
        used.add(identifier)
        if not text.strip():
            errors = errors + ["Empty note"]
        records.append(InputRecord(note=Note(note_id=identifier, text=text), position=position,
                                   original_record=original, errors=errors, warnings=warnings))
    return records
