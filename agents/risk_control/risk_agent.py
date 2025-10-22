"""
prod_metrics/risk_assessment.py

Behavior:
    - Performs a risk assessment for a given project based on:
        - Functional and Non-functional Requirements (FRs/NFRs)
        - Compilation success rate
        - LLM-derived completion rates
    - Calculates an overall risk score and release decision.
"""

import json
from typing import Dict
from sqlalchemy.orm import Session

from util.llm_agent import get_llm_completion
from db import db_operations as db_ops
from db.db_operations import CodeSnapshot

# Thresholds and constants
FR_WEIGHT = 0.5
NFR_WEIGHT = 0.4
COMPILATION_WEIGHT = 0.1
RISK_GO_THRESHOLD = 0.7
RISK_NO_GO_THRESHOLD = 0.5

RISK_LEVELS = {
    "Low": (0.0, 0.4),
    "Medium": (0.4, 0.7),
    "High": (0.7, 1.0)
}


def build_fr_nfr_prompt(snapshot_code: str, fr_list: list[str], nfr_list: list[str]) -> str:
    """
    Builds a structured prompt for the LLM to assess FR/NFR completion rates.
    :param snapshot_code: The current code snapshot text
    :param fr_list: List of functional requirements
    :param nfr_list: List of non-functional requirements
    :return: JSON prompt string
    """
    return f"""
        You are a software quality analyst.
        Task: Given the source code snapshot and project requirements, 
        estimate completion percentages for Functional and Non-Functional Requirements.

        Return a JSON object with:
        - fr_completion_rate (0-1)
        - nfr_completion_rate (0-1)
        - confidence (0-1)
        - rationale (brief explanation)

        Functional Requirements (FRs):
        {json.dumps(fr_list, indent=2)}

        Non-Functional Requirements (NFRs):
        {json.dumps(nfr_list, indent=2)}

        Code Snapshot:
        \"\"\"{snapshot_code[:8000]}\"\"\"  # truncated to prevent token overflow

        Return ONLY the JSON object. Do not include code fences or explanations.
    """


def build_compilation_prompt(snapshot_code: str, language: str) -> str:
    """
    Builds an LLM prompt to estimate the likelihood that the code compiles successfully.
    :param snapshot_code: The source code snapshot text
    :param language: Programming language (e.g., Python, Java, PHP)
    :return: Structured LLM prompt string
    """
    return f"""
        You are a compiler simulation assistant.
        Task: Review the following {language} code and estimate how likely it is to compile successfully 
        without syntax or structural errors.

        Return a JSON object with:
        - compilation_success_rate (0-1)
        - confidence (0-1)
        - rationale (brief explanation)

        Code:
        \"\"\"{snapshot_code[:6000]}\"\"\"

        Notes:
        - Focus on syntax correctness, missing imports, unclosed structures, or language misuse.
        - Do not actually execute the code.
        - Return ONLY the JSON object. No extra text or explanations.
    """


def classify_risk_level(score: float) -> str:
    """
    Classifies risk score into Low, Medium, or High.
    :param score: Calculated numeric risk score (0–1)
    :return: Risk level string
    """
    for level, (low, high) in RISK_LEVELS.items():
        if low <= score < high:
            return level
    return "Unknown"


def calculate_risk(db: Session, project_id: str, language: str) -> Dict:
    """
    Performs end-to-end risk assessment for the given project.

    Steps:
        1. Get latest code snapshot
        2. Retrieve FRs/NFRs
        3. LLM-based compilation success rate
        4. LLM-based FR/NFR completion analysis
        5. Compute overall risk score
        6. Save assessment and return results
    """

    # Retrieve latest code snapshot and requirements
    current_snapshot: CodeSnapshot = db_ops.get_latest_snapshot_by_project(db, project_id)
    if current_snapshot is None:
        raise ValueError(f"Latest snapshot for project {project_id} not found in database.")

    fr_list_dto = db_ops.get_functional_requirements_by_project(db, project_id)
    nfr_list_dto = db_ops.get_non_functional_requirements_by_project(db, project_id)
    fr_list = [fr.description for fr in fr_list_dto]
    nfr_list = [nfr.description for nfr in nfr_list_dto]
    if not fr_list and not nfr_list:
        raise ValueError(f"No requirements (FR/NFR) found for project {project_id}.")

    # Compilation success estimation (via LLM)
    compilation_prompt = build_compilation_prompt(current_snapshot.code_text, language)
    compilation_output = get_llm_completion(compilation_prompt)
    try:
        comp_parsed = json.loads(compilation_output)
        compilation_success_rate = float(comp_parsed.get("compilation_success_rate", 0.0))
        comp_confidence = float(comp_parsed.get("confidence", 0.0))
        comp_rationale = comp_parsed.get("rationale", "")
    except Exception as e:
        print(f"LLM compilation parsing error: {compilation_output[:200]} | error={e}")
        compilation_success_rate = comp_confidence = 0.0
        comp_rationale = f"Parsing error: {e}"

    # LLM-based FR/NFR completion analysis
    fr_prompt = build_fr_nfr_prompt(current_snapshot.code_text, fr_list, nfr_list)
    raw_output = get_llm_completion(fr_prompt)
    try:
        req_parsed = json.loads(raw_output)
        fr_completion_rate = float(req_parsed.get("fr_completion_rate", 0.0))
        nfr_completion_rate = float(req_parsed.get("nfr_completion_rate", 0.0))
        req_confidence = float(req_parsed.get("confidence", 0.0))
        req_rationale = req_parsed.get("rationale", "")
    except Exception as e:
        print(f"LLM FR/NFR parsing error: {raw_output[:200]} | error={e}")
        fr_completion_rate = nfr_completion_rate = req_confidence = 0.0
        req_rationale = f"Parsing error: {e}"

    # Risk computation
    risk_numeric = (
            FR_WEIGHT * (1 - fr_completion_rate) +
            NFR_WEIGHT * (1 - nfr_completion_rate) +
            COMPILATION_WEIGHT * (1 - compilation_success_rate)
    )

    risk_score = round(risk_numeric, 2)
    risk_level = classify_risk_level(risk_score)

    if risk_score >= RISK_GO_THRESHOLD:
        release_decision = "Release"
    elif risk_score <= RISK_NO_GO_THRESHOLD:
        release_decision = "Do Not Release"
    else:
        release_decision = "Conditionally Release"

    fr_score = round(fr_completion_rate, 2)
    nfr_score = round(nfr_completion_rate, 2)
    compilation_score = round(compilation_success_rate, 2)
    rationale = f"Compilation: {comp_rationale}\nFR/NFR: {req_rationale}"

    risk_data = {
        "risk_level": risk_level,
        "release_decision": release_decision,
        "fr_completion_rate": fr_score,
        "nfr_completion_rate": nfr_score,
        "compilation_success_rate": compilation_score,
        "risk_score": round(risk_score * 100, 1),
        "rationale": rationale,
        "compilation_confidence": comp_confidence,
        "requirements_coverage_confidence": req_confidence,
    }

    # Persist results
    db_ops.create_risk_assessment(
        db,
        project_id,
        current_snapshot.commit_id,
        fr_score,
        nfr_score,
        compilation_score,
        risk_score,
        release_decision,
        rationale
    )

    return risk_data
