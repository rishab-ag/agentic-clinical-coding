"""Loss-accounted UTF-8 input records; no clinical interpretation."""
import base64
import csv
import io
import json
import math
import re
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


TEXT_FIELDS = ("note", "note_text", "consult_note", "content", "body", "narrative", "free_text")
DELIMITER = re.compile(r"(?m)^[ \t]*(?:-{3,}|={3,}|\*{3,}|_{3,}|#{3,})[ \t]*\r?\n?")


def _id_key(key):
    return key.casefold().endswith("id")


def _label(key):
    return json.dumps(key[:40], ensure_ascii=True)


def _object_record(item):
    """Locate ID and note text in an object; anything inferred is reported as a warning."""
    warnings = []
    identifier = item.get("note_id")
    if not isinstance(identifier, str) or not identifier.strip():
        for key, value in item.items():
            if _id_key(key) and isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
                identifier = str(value)
                warnings.append(f"Note ID read from field {_label(key)}")
                break
    if isinstance(item.get("text"), str):
        return identifier, item["text"], warnings, []
    strings = {key: value for key, value in item.items() if isinstance(value, str) and not _id_key(key)}
    named = [key for key in strings if key.casefold().replace("-", "_").replace(" ", "_") in TEXT_FIELDS]
    key = named[0] if named else max(strings, key=lambda name: len(strings[name]), default=None)
    if key is None:
        return identifier, json.dumps(item, ensure_ascii=False), warnings, ["Note record text must be a string"]
    how = "" if named else " (longest text field; no recognised note field name)"
    return identifier, strings[key], warnings + [f"Note text read from field {_label(key)}{how}"], []


def _sniff(raw):
    """Unknown extension: decide by content only; plain text is the fallback."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "txt"
    try:
        if isinstance(_json(text), (dict, list)):
            return "json"
    except ValueError:
        pass
    lines = [line for line in text.splitlines() if line.strip()]
    try:
        if lines and all(isinstance(_json(line), dict) for line in lines):
            return "jsonl"
    except ValueError:
        pass
    return "txt"


def read_records(path: Path) -> List[InputRecord]:
    """One result per JSONL line, JSON element, CSV row, delimited TXT note, or file error."""
    try:
        raw = path.read_bytes()
    except OSError:
        return [InputRecord(note=Note(note_id="record-000001", text=""), position=1,
                            original_record={"input_path": str(path)}, errors=["Input file cannot be read"])]
    extension = path.suffix.casefold()
    kind = {".txt": "txt", ".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl", ".csv": "csv", ".tsv": "csv"}.get(extension)
    file_warnings = []
    if kind is None:
        kind = _sniff(raw)
        file_warnings.append(f"Unrecognised input extension; content read as {kind.upper()}")
    parts = raw.splitlines(keepends=True) if kind == "jsonl" else [raw]
    if not parts:
        parts = [b""]
    parsed = []  # (identifier, text, original, errors, warnings)
    for part in parts:
        try:
            text = part.decode("utf-8-sig" if part is parts[0] else "utf-8")
        except UnicodeDecodeError:
            parsed.append((None, part.decode("utf-8", errors="replace"),
                           {"raw_bytes_base64": base64.b64encode(part).decode("ascii")}, ["Input record is not valid UTF-8"], []))
            continue
        if kind == "txt":
            chunks = [chunk for chunk in DELIMITER.split(text) if chunk.strip()]
            if len(chunks) > 1:
                note = f"Plain-text file split into {len(chunks)} notes at delimiter lines"
                parsed.extend((None, chunk, chunk, [], [note]) for chunk in chunks)
            else:
                parsed.append((None, text, text, [], []))
            continue
        if kind == "csv":
            try:
                rows = [{key: value for key, value in row.items() if isinstance(key, str)}
                        for row in csv.DictReader(io.StringIO(text, newline=""), delimiter="\t" if extension == ".tsv" else ",")]
            except csv.Error:
                rows = None
            if not rows:
                parsed.append((None, text, text, ["CSV has no readable header and data rows"], []))
            for row in rows or []:
                identifier, value, warnings, errors = _object_record(row)
                parsed.append((identifier, value, row, errors, warnings))
            continue
        try:
            obj = _json(text)
        except ValueError:
            parsed.append((None, text, text, ["Malformed or empty JSON record/document"], []))
            continue
        objects, wrapper = [obj], []
        if kind == "json" and isinstance(obj, list):
            objects = obj
        elif kind == "json" and isinstance(obj, dict) and _object_record(obj)[3]:
            lists = [key for key, value in obj.items() if isinstance(value, list)]
            if len(lists) == 1:
                objects, wrapper = obj[lists[0]], [f"Records read from wrapper field {_label(lists[0])}"]
        if not objects:
            parsed.append((None, "", obj, ["Empty JSON array: no note records supplied"], []))
        for item in objects:
            if isinstance(item, str):
                parsed.append((None, item, item, [], wrapper))
            elif not isinstance(item, dict):
                parsed.append((None, json.dumps(item, ensure_ascii=False), item, ["Note record must be an object or string with note text"], wrapper))
            else:
                identifier, value, warnings, errors = _object_record(item)
                parsed.append((identifier, value, item, errors, wrapper + warnings))
    reserved = {identifier for identifier, _, _, _, _ in parsed if isinstance(identifier, str) and identifier.strip()}
    used = set()
    records = []
    for position, (identifier, text, original, errors, found) in enumerate(parsed, 1):
        warnings = file_warnings + list(found)
        if not isinstance(identifier, str) or not identifier.strip() or identifier in used:
            if kind != "txt":
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
