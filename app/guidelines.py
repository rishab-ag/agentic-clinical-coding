"""Offline cache validation and source-by-source human review export."""
import argparse
import json
import sys
from pathlib import Path

from app.constraints import DEFAULT_CACHE, load_constraint_cache, payload_sha256
from app.data import DATA_DIR, load_supplied_data
from app.trust import scan_untrusted_text


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline guideline normalization review workflow")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--review-report", action="store_true", help="Print one JSONL review object per source; does not approve records")
    args = parser.parse_args(argv)
    try:
        data = load_supplied_data(args.data_dir)
        cache = load_constraint_cache(data, args.cache)
    except (OSError, ValueError) as error:
        print(f"Constraint validation failed: {error}", file=sys.stderr)
        return 1
    counts = {status: sum(r.verification_status == status for r in cache.records)
              for status in ("verified", "uncertain", "rejected")}
    print(f"Validated {len(cache.records)} records across {len(data.guidelines)} sources: {counts}", file=sys.stderr)
    if args.review_report:
        for source in data.guidelines:
            records = [r for r in cache.records if r.source.source_id == source.id]
            print(json.dumps(dict(source=source.model_dump(), trust_scan=scan_untrusted_text(source.text).model_dump(),
                                  records=[dict(record=r.model_dump(), payload_sha256=payload_sha256(r)) for r in records]),
                             ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
