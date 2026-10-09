"""Load immutable supplied data, with exact byte hashes and structural checks."""
import hashlib
import json
from pathlib import Path
from typing import List, Literal

from pydantic import Field

from app.models import Contract

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class CatalogueEntry(Contract):
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    chapter: str = Field(min_length=1)
    synonyms: List[str]
    catalogue_origin: Literal["supplied"] = "supplied"


class GuidelineSnippet(Contract):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    effective: str = Field(pattern=r"^\d{4}-\d{2}$")
    text: str = Field(min_length=1)


class SuppliedData(Contract):
    catalogue: List[CatalogueEntry]
    guidelines: List[GuidelineSnippet]
    catalogue_sha256: str
    guidelines_sha256: str


def _load(path, model, count, identifier):
    raw = path.read_bytes()
    records = json.loads(raw)
    if not isinstance(records, list) or len(records) != count:
        raise ValueError(f"{path.name}: expected {count} records")
    entries = [model.model_validate(record) for record in records]
    if len({getattr(entry, identifier) for entry in entries}) != count:
        raise ValueError(f"{path.name}: duplicate {identifier}")
    return entries, hashlib.sha256(raw).hexdigest()


def load_supplied_data(data_dir: Path = DATA_DIR) -> SuppliedData:
    catalogue, catalogue_hash = _load(data_dir / "icd_catalog.json", CatalogueEntry, 404, "code")
    guidelines, guideline_hash = _load(data_dir / "guideline_snippets.json", GuidelineSnippet, 45, "id")
    return SuppliedData(catalogue=catalogue, guidelines=guidelines,
                        catalogue_sha256=catalogue_hash, guidelines_sha256=guideline_hash)
