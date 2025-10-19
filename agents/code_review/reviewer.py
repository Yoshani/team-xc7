"""
agents/code_review/reviewer.py

This module contains the fully functional core logic for the Code Review Agent.
It fetches context from the database, runs static analysis, calls the LLM (Groq)
for an intelligent review, and saves the structured suggestions.
"""

import subprocess
import tempfile
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.connection import get_db
from db import db_operations as db_ops
from .llm_agent import get_llm_completion
from util.helper import safe_json_parse

router = APIRouter()

class CodeReviewRequest(BaseModel):
    commit_id: str
    project_id: str
    code_text: str
    language: str

def run_static_analysis(code: str, language: str) -> list:
    """Runs a basic linter on the given code and returns issues."""
    issues = []
    if language.lower() == "php":
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.php', delete=False) as temp_file:
            temp_file.write(code)
            file_path = temp_file.name
        try:
            subprocess.run(['php', '-l', file_path], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            issues.append({"source": "php_linter", "error": e.stdout.strip()})
        except FileNotFoundError:
            issues.append({"source": "system_error", "error": "PHP command not found."})
        finally:
            os.remove(file_path)
    return issues

def build_review_prompt(code: str, language: str, static_issues: list, nfrs: list) -> str:
    """Builds a detailed, structured prompt for the LLM to perform a code review."""
    nfr_list_str = "\n".join([f"- {nfr.category}: {nfr.description}" for nfr in nfrs]) if nfrs else "No NFRs provided."
    static_issues_str = "\n".join([f"- {issue['source']}: {issue.get('error', issue.get('message'))}" for issue in static_issues]) if static_issues else "No issues found by static analysis."

    return f"""
    You are an expert Senior Software Developer acting as an automated code reviewer.
    Your task is to provide helpful, structured code review suggestions for the given code snippet.

    **Instructions:**
    1. Analyze the provided code snippet.
    2. Consider the project's Non-Functional Requirements (NFRs) listed below.
    3. Consider the results from the basic static analysis tools.
    4. Identify potential bugs, security vulnerabilities, performance issues, or style violations.
    5. For each issue you find, provide a clear suggestion for how to fix it.
    6. Return your findings as a JSON object containing a list of suggestions.

    **Project Context:**
    - Language: {language}
    - Non-Functional Requirements (NFRs):
    {nfr_list_str}
    - Static Analysis Results:
    {static_issues_str}

    **Code to Review:**
    ```php
    {code}
    ```

    **Output Format:**
    Return ONLY a single, valid JSON object with a single key "suggestions".
    The value of "suggestions" should be a list of objects, where each object has the following fields:
    - "line_start": (integer) The starting line number of the issue.
    - "line_end": (integer) The ending line number of the issue.
    - "suggestion": (string) A clear, concise comment explaining the issue and how to fix it. This comment must reference the specific NFR if it's relevant.
    - "severity": (string) One of: "Low", "Medium", "High", or "Critical".

    Do NOT include any explanations or markdown fences in your response. Return ONLY the JSON object.
    """

@router.post("/review", tags=["Code Review"])
def start_code_review(request: CodeReviewRequest, db: Session = Depends(get_db)):
    """The main API endpoint for the Code Review Agent."""
    print(f"Code Review Agent: Received request for commit: {request.commit_id}")

    static_analysis_issues = run_static_analysis(request.code_text, request.language)
    print(f"Code Review Agent: Static analysis found {len(static_analysis_issues)} issues.")

    project_nfrs = db_ops.get_non_functional_requirements_by_project(db, request.project_id)
    print(f"Code Review Agent: Found {len(project_nfrs)} NFRs for context.")

    prompt = build_review_prompt(request.code_text, request.language, static_analysis_issues, project_nfrs)
    raw_llm_output = get_llm_completion(prompt)
    print("Code Review Agent: Received response from LLM.")

    parsed_output = safe_json_parse(raw_llm_output)
    llm_suggestions = parsed_output.get("suggestions", [])
    print(f"Code Review Agent: LLM generated {len(llm_suggestions)} suggestions.")

    saved_suggestions_ids = []
    for suggestion in llm_suggestions:
        new_suggestion = db_ops.create_review(
            db=db,
            commit_id=request.commit_id,
            line_start=suggestion.get("line_start"),
            line_end=suggestion.get("line_end"),
            suggestion=suggestion.get("suggestion", "N/A"),
            severity=suggestion.get("severity", "Medium")
        )
        saved_suggestions_ids.append(new_suggestion.review_id)
    print(f"Code Review Agent: Successfully saved {len(saved_suggestions_ids)} suggestions to the database.")

    return {
        "message": "Code review analysis complete.",
        "commit_id": request.commit_id,
        "static_analysis_results": static_analysis_issues,
        "llm_review_suggestions": llm_suggestions,
        "saved_review_ids": saved_suggestions_ids
    }

