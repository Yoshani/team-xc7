"""
agents/code_review/reviewer.py

This module contains the fully functional core logic for the Code Review Agent.
It saves a new code snapshot, fetches context from the database, runs static analysis,
calls the LLM (Groq) for an intelligent review, and saves the structured suggestions.
"""
import os
import py_compile
import shutil
import subprocess
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import db_operations as db_ops
from db.connection import get_db
from util.helper import safe_json_parse
from .llm_agent import get_llm_completion

router = APIRouter()


class CodeReviewRequest(BaseModel):
    parent_commit_id: Optional[str] = None
    commit_id: str
    project_id: str
    developer_name: str
    code_text: str
    language: str


def run_static_analysis(code: str, language: str) -> list:
    """
    Runs a basic static analysis (linter) for the given code and language.
    :param code: The source code to analyze.
    :param language: Programming language (e.g., "php", "python", or "javascript").
    :return: A list of detected issues or messages.
    """
    issues = []
    language = language.lower()

    # --- PHP ---
    if language == "php":
        php_path = shutil.which("php")
        if not php_path or not os.path.exists(php_path):
            return [{"source": "system_error", "error": "PHP command not found."}]

        with tempfile.NamedTemporaryFile(mode='w+', suffix='.php', delete=False) as temp_file:
            temp_file.write(code)
            file_path = temp_file.name

        try:
            result = subprocess.run(
                [php_path, "-l", file_path],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                issues.append({
                    "source": "php_linter",
                    "error": result.stdout.strip() or result.stderr.strip()
                })
        except Exception as e:
            issues.append({"source": "system_error", "error": str(e)})
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        if not issues:
            issues.append({"source": "php_linter", "message": "No syntax errors detected."})

    # --- PYTHON ---
    elif language == "python":
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as temp_file:
            temp_file.write(code)
            file_path = temp_file.name

        try:
            py_compile.compile(file_path, doraise=True)
            issues.append({"source": "python_compile", "message": "No syntax errors detected."})

            # Optional flake8 check
            flake8_path = shutil.which("flake8")
            if flake8_path:
                result = subprocess.run(
                    [flake8_path, file_path],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    for line in result.stdout.strip().split("\n"):
                        issues.append({"source": "flake8", "warning": line})
        except py_compile.PyCompileError as e:
            issues.append({"source": "python_compile", "error": str(e)})
        except Exception as e:
            issues.append({"source": "system_error", "error": str(e)})
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    # --- JAVASCRIPT ---
    elif language in ["javascript", "js"]:
        node_path = shutil.which("node")
        if not node_path or not os.path.exists(node_path):
            return [{"source": "system_error", "error": "Node.js command not found."}]

        with tempfile.NamedTemporaryFile(mode='w+', suffix='.js', delete=False) as temp_file:
            temp_file.write(code)
            file_path = temp_file.name

        try:
            # Basic syntax check using node --check
            result = subprocess.run(
                [node_path, "--check", file_path],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                issues.append({
                    "source": "node_check",
                    "error": result.stderr.strip() or result.stdout.strip()
                })
            else:
                issues.append({"source": "node_check", "message": "No syntax errors detected."})

            # Optional: ESLint if installed
            eslint_path = shutil.which("eslint")
            if eslint_path:
                result = subprocess.run(
                    [eslint_path, file_path, "--no-color"],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    for line in result.stdout.strip().split("\n"):
                        issues.append({"source": "eslint", "warning": line})
        except Exception as e:
            issues.append({"source": "system_error", "error": str(e)})
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    # --- UNKNOWN LANGUAGE ---
    else:
        issues.append({"source": "static_analysis", "message": f"No linter configured for '{language}'."})

    return issues


def build_review_prompt(code: str, language: str, static_issues: list, nfrs: list) -> str:
    """Builds a detailed, structured prompt for the LLM to perform a code review."""
    nfr_list_str = "\n".join([f"- {nfr.category}: {nfr.description}" for nfr in nfrs]) if nfrs else "No NFRs provided."
    static_issues_str = "\n".join([f"- {issue['source']}: {issue.get('error', issue.get('message'))}" for issue in
                                   static_issues]) if static_issues else "No issues found by static analysis."

    # Prompt remains the same
    return f"""
    You are an expert Senior Software Developer acting as an automated code reviewer.
    Your task is to provide helpful, structured code review suggestions for the given code snippet.

    **Instructions:**
    1. Analyze the provided code snippet.
    2. Consider the project's Non-Functional Requirements (NFRs) listed below.
    3. Consider the results from the basic static analysis tools.
    4. Identify potential bugs, security vulnerabilities, performance issues, or style violations.
    5. Return your findings as a JSON object containing a list of suggestions.

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
    The value of "suggestions" should be a list of objects with the following fields:
    - "line_start": (integer) The starting line number of the issue.
    - "line_end": (integer) The ending line number of the issue.
    - "suggestion": (string) A clear, concise comment explaining the issue and how to fix it.
    - "severity": (string) One of: "Low", "Medium", "High", or "Critical".

    Do NOT include any explanations or markdown fences in your response.
    """


@router.post("/review", tags=["Code Review"])
def start_code_review(request: CodeReviewRequest, db: Session = Depends(get_db)):
    """The main API endpoint for the Code Review Agent."""
    print(f"Code Review Agent: Received request based on parent commit: {request.parent_commit_id}")

    new_snapshot = db_ops.create_snapshot(
        db=db,
        project_id=request.project_id,
        commit_id=request.commit_id,
        parent_commit_id=request.parent_commit_id,
        developer_name=request.developer_name,
        code_text=request.code_text,
        language=request.language
    )
    print(f"Code Review Agent: Successfully created new snapshot with commit_id: {new_snapshot.commit_id}")

    static_analysis_issues = run_static_analysis(request.code_text, request.language)
    print(f"Code Review Agent: Static analysis found {len(static_analysis_issues)} issues.")

    project_nfrs = db_ops.get_non_functional_requirements_by_project(db, request.project_id)
    print(f"Code Review Agent: Found {len(project_nfrs)} NFRs for context.")

    prompt = build_review_prompt(request.code_text, request.language, static_analysis_issues, project_nfrs)
    raw_llm_output = get_llm_completion(prompt)
    print("Code Review Agent: Received response from LLM.")

    # Parse the AI's JSON response safely.
    parsed_output = safe_json_parse(raw_llm_output)
    llm_suggestions = parsed_output.get("suggestions", [])
    print(f"Code Review Agent: LLM generated {len(llm_suggestions)} suggestions.")

    saved_suggestions_ids = []
    for suggestion in llm_suggestions:
        # Ensure line_start and line_end are integers or None
        line_start = suggestion.get("line_start")
        line_end = suggestion.get("line_end")
        try:
            line_start = int(line_start) if line_start is not None else None
        except (ValueError, TypeError):
            line_start = None
        try:
            line_end = int(line_end) if line_end is not None else None
        except (ValueError, TypeError):
            line_end = None

        new_suggestion = db_ops.create_review(
            db=db,
            commit_id=request.commit_id,
            line_start=line_start,
            line_end=line_end,
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
