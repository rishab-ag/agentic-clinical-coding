"""Opt-in live evaluation; pending labels never trigger inference."""
import argparse
import json
import os
from pathlib import Path

from app.data import load_supplied_data
from app.evaluation import DEFAULT_FIXTURES, evaluate_callable, load_fixtures
from app.ingestion import InputRecord
from app.model_provider import model_from_environment


def main(argv=None):
    parser=argparse.ArgumentParser(description="Opt-in two-stage live evaluation")
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--fixtures",type=Path,default=DEFAULT_FIXTURES)
    parser.add_argument("--split",choices=["development","held_out"],default="development")
    args=parser.parse_args(argv)
    reason=None
    if not args.live:
        reason="Live evaluation disabled; explicit --live required"
    provider=os.environ.get("MODEL_PROVIDER", "").strip().lower() or (
        "gemini" if os.environ.get("GEMINI_API_KEY", "").strip() and not os.environ.get("OPENAI_API_KEY", "").strip() else "openai")
    prefix=provider.upper()
    if args.live and not os.environ.get(prefix+"_API_KEY", "").strip():
        reason="Selected provider API key absent; no model call attempted"
    elif args.live and (not os.environ.get(prefix+"_MODEL", "").strip() or not os.environ.get(prefix+"_CONTEXT_LIMIT", "").strip()):
        reason="Model/context not configured; no model call attempted"
    if reason:
        print(json.dumps(dict(type="live_evaluation",status="skipped",reason=reason,model_calls=0)))
        return 0
    try:
        data=load_supplied_data()
        fixtures=load_fixtures(args.fixtures,data)
        approved=[f for f in fixtures.fixtures if f.review_status=="human_approved" and f.split==args.split]
        if not approved:
            print(json.dumps(dict(type="live_evaluation",status="skipped",reason="No human-approved fixtures in selected split",model_calls=0)))
            return 0
        from app.reasoning import ModelPipeline
        model=model_from_environment()
        pipeline=ModelPipeline(data,model)
        position=0
        def decide(note):
            nonlocal position
            position+=1
            return pipeline.process(InputRecord(note=note,position=position,
                original_record={"note_id":note.note_id,"text":note.text}))
        report=evaluate_callable(approved,decide,data)
        report["evaluation_kind"]="live_model_against_human_rubric"
        report["split"]=args.split
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    except (OSError,ValueError):
        print(json.dumps(dict(type="live_evaluation",status="error",reason="Invalid fixture/model configuration")))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
