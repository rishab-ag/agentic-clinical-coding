"""Opt-in live-evaluation stub; no inference or provider is implemented yet."""
import argparse
import json
import os


def main(argv=None):
    parser = argparse.ArgumentParser(description="Opt-in live evaluation (Milestone 3 stub)")
    parser.add_argument("--live", action="store_true", help="Explicitly opt in to future billable model evaluation")
    parser.add_argument("--fixtures", help="Reserved path to independently human-labeled fixtures")
    args = parser.parse_args(argv)
    if not args.live:
        reason = "Live evaluation disabled; explicit --live required"
    elif not os.environ.get("OPENAI_API_KEY", "").strip():
        reason = "OPENAI_API_KEY absent; no model call attempted"
    else:
        reason = "Live provider/pipeline not implemented in Milestone 3; no model call attempted"
    print(json.dumps(dict(type="live_evaluation", status="skipped", reason=reason, model_calls=0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
