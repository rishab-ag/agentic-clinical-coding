"""Real opt-in inference only with independently approved fixtures."""
import os

import pytest

from app.data import load_supplied_data
from app.evaluation import DEFAULT_FIXTURES,evaluate_callable,load_fixtures
from app.ingestion import InputRecord
from app.model_provider import model_from_environment
from app.reasoning import ModelPipeline


@pytest.mark.skipif(os.environ.get("RUN_LIVE_EVAL")!="1" or not os.environ.get("OPENAI_API_KEY"),
                    reason="Live evaluation requires explicit RUN_LIVE_EVAL=1 and an API key")
def test_real_two_stage_evaluation():
    data=load_supplied_data()
    selected=[f for f in load_fixtures(DEFAULT_FIXTURES,data).fixtures
              if f.review_status=="human_approved" and f.split=="development"]
    if not selected:
        pytest.skip("No independently human-approved development fixtures")
    if not os.environ.get("OPENAI_MODEL") or not os.environ.get("OPENAI_CONTEXT_LIMIT"):
        pytest.skip("Model/context configuration missing")
    pipeline=ModelPipeline(data,model_from_environment())
    observed=[]
    def decide(note):
        result=pipeline.process(InputRecord(note=note,position=len(observed)+1,original_record=note.model_dump()))
        observed.append(result)
        return result
    report=evaluate_callable(selected,decide,data)
    assert all("decide" in result.provenance.stage_prompt_tokens for result in observed), "Actual two-stage inference did not complete"
    assert report["passed"], report
