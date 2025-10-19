from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.prod_metrics.classify_reviews import classify_commits
from agents.prod_metrics.generate_metrics import calculate_metrics
from agents.code_review.reviewer import router as code_review_router
from db.connection import get_db
from db import db_operations as db_ops

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

app.include_router(code_review_router, prefix="/agents")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
