"""Offline note-file CLI; stdout/output are JSONL, diagnostics are stderr."""
import argparse
import sys
from pathlib import Path

from app.data import DATA_DIR, load_supplied_data
from app.models import CodingResult, Confidence, Provenance
from app.ingestion import read_records
from app.pipeline import NoKeyPipeline
from app.model_provider import model_from_environment


def main(argv=None):
    parser = argparse.ArgumentParser(description="Clinical coding prototype (conservative offline pipeline)")
    parser.add_argument("--input", type=Path, help="Arbitrary TXT, JSON or JSONL note file")
    parser.add_argument("--output", type=Path, help="Also write the same JSONL to this path")
    parser.add_argument("--no-model", action="store_true", help="Force offline mode even when credentials exist")
    parser.add_argument("--check-data", action="store_true", help="Validate supplied corpus and print counts/hashes to stderr")
    parser.add_argument("--self-check", action="store_true", help="Emit one synthetic unresolved bootstrap result as JSONL")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Supplied reference-data directory")
    args = parser.parse_args(argv)
    if args.output and not args.input:
        parser.error("--output requires --input")
    if not args.check_data and not args.self_check and not args.input:
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
    if args.input:
        protected = {args.input.resolve(), (args.data_dir / "icd_catalog.json").resolve(),
                     (args.data_dir / "guideline_snippets.json").resolve()}
        root = Path(__file__).resolve().parent.parent
        protected.update((root / name).resolve() for name in ("data/derived/guideline_constraints.json",
                          "tests/fixtures/clinical_eval.jsonl", "docs/clinical_fixture_review.md"))
        if args.output and (args.output.resolve().is_relative_to(root / "data/expanded") or
                            args.output.resolve().is_relative_to(args.data_dir.resolve() / "expanded")):
            print("Output must not overwrite external source/review records",file=sys.stderr)
            return 1
        if args.output and args.output.resolve() in protected:
            print("Output must not overwrite input or supplied reference files", file=sys.stderr)
            return 1
        records = read_records(args.input)
        pipeline = NoKeyPipeline(data)
        if not args.no_model:
            try:
                model = model_from_environment()
                if model:
                    from app.reasoning import ModelPipeline
                    pipeline = ModelPipeline(data,model)
            except (ValueError, TypeError):
                print("Invalid model configuration; using conservative offline mode", file=sys.stderr)
        output = None
        try:
            if args.output:
                output = args.output.open("w", encoding="utf-8")
            for result in pipeline.run(records):
                line = result.model_dump_json() + "\n"
                if output:
                    output.write(line)
                sys.stdout.write(line)
        except OSError:
            print("Unable to write output", file=sys.stderr)
            return 1
        finally:
            if output:
                output.close()
        return 0
    if args.self_check:
        result = CodingResult(note_id="bootstrap-check", original_note="Synthetic bootstrap check.",
                              status="unresolved", unresolved=["Bootstrap wiring check; no clinical assignment attempted"],
                              confidence=Confidence(level="low", increase_if=["Implement and validate subsequent milestones"]),
                              provenance=Provenance(mode="bootstrap", catalogue_sha256=data.catalogue_sha256,
                                                    guidelines_sha256=data.guidelines_sha256))
        print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
