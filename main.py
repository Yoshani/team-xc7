from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
from starlette.concurrency import run_in_threadpool

from agents.prod_metrics.classify_reviews import classify_commits
from agents.prod_metrics.generate_metrics import calculate_metrics
from db.connection import get_db
from db import db_operations as db_ops
from db.db_operations import save_nfrs_statement_to_description

from agents.nfr_agent.engine import NFRGenerator

try:
    from agents.nfr_agent.engine import DEFAULT_MODEL
except Exception:
    DEFAULT_MODEL = None


class GenerateNFRRequest(BaseModel):
    functional_requirements: List[str] = Field(..., min_items=1)
    domain: Optional[str] = None
    model: Optional[str] = DEFAULT_MODEL
    project_id: Optional[str] = None
    save_to_db: bool = False


TIMEOUT_SECONDS = 45  # fail fast instead of hanging forever

app = FastAPI()


# ---------- Request schema ----------
class SnapshotRequest(BaseModel):
    parent_commit_id: str
    project_id: str
    developer_name: str
    code_text: str
    language: str


# ---------- API endpoints ----------
@app.post("/classify")
async def classify_snapshot(snapshot: SnapshotRequest, db: Session = Depends(get_db)):
    """
    Save merged snapshot, classify parent reviews, and return results.
    :param snapshot: Incoming snapshot data
    :param db: Database session
    :return: Classification results
    """
    # Save the incoming child snapshot
    merged_snapshot = db_ops.create_snapshot(
        db,
        project_id=snapshot.project_id,
        parent_commit_id=snapshot.parent_commit_id,
        developer_name=snapshot.developer_name,
        code_text=snapshot.code_text,
        language=snapshot.language
    )

    # Run classification
    results = classify_commits(db, merged_snapshot.commit_id)

    # Save classifications
    for classification in results:
        db_ops.create_classification(
            db=db,
            review_id=classification["review_id"],
            category=classification["category"],
            classification=classification["classification"],
            recurring_issue=classification["recurring_issue"],
            confidence=classification["confidence"],
            rationale=classification["rationale"]
        )

    return {"classifications": results}


@app.get("/generate_metrics")
async def generate_metrics(db: Session = Depends(get_db)):
    """
    Generate and return productivity metrics.
    :param db: Database session
    :return: Productivity metrics
    """
    suggestions_handled_per_dev, acceptance_rate_per_dev, avg_per_dev_category, dev_recurring_issues, sugesstions_handled_per_team, overall_acceptance_rate, avg_team_category, team_recurring_issues = calculate_metrics(
        db)
    return {"developer_productivity_metrics": {"average_suggestions_handled_per_day": suggestions_handled_per_dev,
                                               "suggestion_acceptance_rate": acceptance_rate_per_dev,
                                               "average_suggestions_handled_per_category_per_day": avg_per_dev_category,
                                               "dev_specific_recurring_issues": dev_recurring_issues},
            "team_productivity_metrics": {"average_suggestions_handled_per_day": sugesstions_handled_per_team,
                                          "overall_suggestion_acceptance_rate": overall_acceptance_rate,
                                          "average_suggestions_handled_per_category_per_day": avg_team_category,
                                          "team_specific_recurring_issues": team_recurring_issues}}


@app.post("/nfr/generate")
async def generate_nfrs(req: GenerateNFRRequest, db: Session = Depends(get_db)):
    """
    Generate NFRs and (optionally) save them to MySQL.
    description := statement
    """
    gen = NFRGenerator(model=req.model or DEFAULT_MODEL)

    async def _do_generate():
        # Run potentially blocking LLM call in a thread
        return await run_in_threadpool(gen.generate, req.functional_requirements, req.domain)

    try:
        result = await asyncio.wait_for(_do_generate(), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"Generation timed out after {TIMEOUT_SECONDS}s")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # The generator may return either key; prefer non_functional_requirements
    nfr_list = result.get("non_functional_requirements") or result.get("nfrs") or []
    if not isinstance(nfr_list, list):
        raise HTTPException(status_code=500, detail="Generator returned an unexpected format for NFRs.")

    rows_saved = 0
    if req.save_to_db:
        if not req.project_id:
            raise HTTPException(status_code=400, detail="project_id is required when save_to_db is true.")
        try:
            rows_saved = save_nfrs_statement_to_description(db, req.project_id, nfr_list)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"DB error: {e}")

    # Attach storage summary to the response
    result["_storage"] = {
        "requested_save": req.save_to_db,
        "project_id": req.project_id,
        "rows_saved": rows_saved
    }
    return result


# (Optional) simple health check
@app.get("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
