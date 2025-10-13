"""
agents/code_review/reviewer.py

This module contains the logic for the Code Review Agent.
For this draft PR, it implements the static analysis step
and uses a placeholder for the LLM review.
"""

import subprocess
import tempfile
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.connection import get_db

# This creates a router, which is like a mini-API just for your agent.
router = APIRouter()

# This defines the data structure your API endpoint will expect to receive.
class CodeReviewRequest(BaseModel):
    commit_id: str
    project_id: str
    code_text: str
    language: str

def run_static_analysis(code: str, language: str) -> list:
    """
    Runs static analysis tools on the given code and returns a list of issues.
    For this draft, we will only implement a basic pylint check for Python.
    """
    issues = []
    # For the MVP, we only handle PHP as per the project scope.
    # We will use a simple linting check as a placeholder for full static analysis.
    # In a real implementation, you would run tools like `php -l` or a proper linter.

    if language.lower() == "php":
        # We need to write the code to a temporary file to lint it.
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.php', delete=False) as temp_file:
            temp_file.write(code)
            file_path = temp_file.name

        try:
            # Run the PHP linter (`php -l`) as a subprocess.
            result = subprocess.run(['php', '-l', file_path], capture_output=True, text=True, check=True)
            # If it runs without error, there are no syntax issues.
            issues.append({"source": "php_linter", "message": "No syntax errors found."})
        except subprocess.CalledProcessError as e:
            # If the linter finds an error, it will exit with a non-zero code.
            # We capture the error message to return it.
            issues.append({"source": "php_linter", "message": e.stdout.strip()})
        except FileNotFoundError:
            issues.append({"source": "system", "message": "PHP command not found. Please ensure PHP is installed and in your PATH."})

    # TODO: Add runners for other static analysis tools like `eslint` for JavaScript or `bandit` for security.
    return issues

def get_llm_review(code: str, analysis_results: list) -> list:
    """
    Placeholder function for calling the LLM (Groq).
    In this draft, it returns a hardcoded, example suggestion to show the intended output format.
    """
    # TODO: Implement the actual Groq API call here.
    # This involves building the prompt with the code, NFRs (from DB), and analysis_results.

    # This is a mock response.
    mock_suggestion = {
        "suggestion_id": "LLM-SUG-001",
        "line_start": 2,
        "line_end": 2,
        "issue": "Input validation missing",
        "rationale": "As per security NFRs, all user inputs should be validated to prevent errors or attacks.",
        "suggestion_comment": "Consider using a function like `intval()` to ensure the inputs `$a` and `$b` are integers before performing the addition."
    }
    return [mock_suggestion]


@router.post("/review")
def start_code_review(request: CodeReviewRequest, db: Session = Depends(get_db)):
    """
    API endpoint for the Code Review Agent.
    It receives code, runs static analysis, gets a (mock) LLM review, and returns the results.
    """
    print(f"Code Review Agent received request for commit: {request.commit_id}")

    # Step 1: Run static analysis.
    static_analysis_issues = run_static_analysis(request.code_text, request.language)

    # Step 2: Get a review from the LLM (currently a placeholder).
    # TODO: Fetch FRs and NFRs from the database to pass to the LLM.
    llm_suggestions = get_llm_review(request.code_text, static_analysis_issues)

    # TODO: Save the suggestions to the database using `db_operations`.

    return {
        "message": "Code review analysis complete.",
        "static_analysis_results": static_analysis_issues,
        "llm_review_suggestions": llm_suggestions
    }
