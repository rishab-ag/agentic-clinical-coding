"""Bootstrap CLI. Note ingestion and coding are deliberately not implemented yet."""
import argparse
import sys
from pathlib import Path

from app.data import DATA_DIR, load_supplied_data
from app.models import CodingResult, Confidence, Provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description="Clinical coding prototype (Milestone 1 scaffold)")
    parser.add_argument("--check-data", action="store_true", help="Validate supplied corpus and print counts/hashes to stderr")
    parser.add_argument("--self-check", action="store_true", help="Emit one synthetic unresolved bootstrap result as JSONL")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Supplied reference-data directory")
    args = parser.parse_args(argv)
    if not args.check_data and not args.self_check:
        parser.print_help()
        return 0
    try:
        data = load_supplied_data(args.data_dir)
    except (OSError, ValueError) as error:
        print(f"Data validation failed: {error}", file=sys.stderr)
        return 1
    if args.check_data:
        print(f"Catalogue: {len(data.catalogue)} unique codes; SHA-256 {data.catalogue_sha256}", file=sys.stderr)
        print(f"Guidelines: {len(data.guidelines)} unique IDs; SHA-256 {data.guidelines_sha256}", file=sys.stderr)
    if args.self_check:
        result = CodingResult(note_id="bootstrap-check", original_note="Synthetic bootstrap check.",
                              status="unresolved", unresolved=["Clinical pipeline not implemented in Milestone 1"],
                              confidence=Confidence(level="low", increase_if=["Implement and validate subsequent milestones"]),
                              provenance=Provenance(mode="bootstrap", catalogue_sha256=data.catalogue_sha256,
                                                    guidelines_sha256=data.guidelines_sha256))
        print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
