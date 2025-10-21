# agents/risk_control/risk_agent.py

from __future__ import annotations
from typing import Optional, Dict
from sqlalchemy.orm import Session
from database import db_operations as db_ops

# Weights per spec
W_FRC = 0.5
W_NFRC = 0.4
W_CSR = 0.1

def _clip01(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if f < 0 else 1.0 if f > 1 else f

def _release_decision(score: float) -> str:
    # < 33: Go, 33–66: Conditional, > 66: No-Go
    if score < 33:
        return "Go"
    if score <= 66:
        return "Conditional"
    return "No-Go"

def _risk_level(score: float) -> str:
    if score < 33:
        return "Low Risk"
    if score <= 66:
        return "Medium Risk"
    return "High Risk"

def calculate_risk_score(
    db: Session,
    *,
    commit_id: Optional[str] = None,
    project_id: Optional[str] = None,
    persist: bool = True
) -> Dict:
    """
    Risk = 100 × [0.5×(1−FRC) + 0.4×(1−NFRC) + 0.1×(1−CSR)]
    FRC/NFRC/CSR expected in productivity_metrics as normalized rates [0..1]:
      - fr_completion_rate
      - nfr_completion_rate
      - compilation_success_rate
    If commit_id is not provided, latest commit_id for the project is used.
    """
    if not commit_id:
        if not project_id:
            raise ValueError("Either commit_id or project_id must be provided.")
        latest = db_ops.get_latest_commit_for_project(db, project_id)
        if not latest:
            raise ValueError(f"No commits found for project_id={project_id}")
        commit_id = latest.commit_id

    metric_names = [
        "fr_completion_rate",
        "nfr_completion_rate",
        "compilation_success_rate",
    ]
    metrics_map = db_ops.get_productivity_metrics_map(db, commit_id, metric_names)

    frc = _clip01(metrics_map.get("fr_completion_rate"))
    nfrc = _clip01(metrics_map.get("nfr_completion_rate"))
    csr = _clip01(metrics_map.get("compilation_success_rate"))

    risk_score = 100.0 * (W_FRC * (1 - frc) + W_NFRC * (1 - nfrc) + W_CSR * (1 - csr))
    risk_score = round(risk_score, 2)

    result = {
        "commit_id": commit_id,
        "fr_completion_rate": round(frc, 4),
        "nfr_completion_rate": round(nfrc, 4),
        "compilation_success_rate": round(csr, 4),
        "risk_score": risk_score,
        "risk_level": _risk_level(risk_score),
        "release_decision": _release_decision(risk_score),
        "rationale": (
            "Risk Score = 100 × (0.5 × (1 − FRC) + 0.4 × (1 − NFRC) + 0.1 × (1 − CSR))"
        ),
    }

    if persist:
        # store percentages in risk_assessments for readability
        db_ops.insert_risk_assessment(
            db=db,
            commit_id=commit_id,
            frc=frc,
            nfrc=nfrc,
            csr=csr,
            final_score=risk_score,
            recommendation=result["release_decision"],
            rationale=result["rationale"],
        )

    return result
