"""
prod_metrics/classify_reviews.py

Behavior:
    - Attempts to call a remote LLM to classify reviews.
"""

import json
from typing import Tuple, List, Dict

from sqlalchemy.orm import Session

from agents.prod_metrics.constants import REVIEW_CATEGORIES, CLASSIFICATION_ACCEPTED, CLASSIFICATION_MODIFIED, \
    CLASSIFICATION_REJECTED
from util.llm_agent import get_llm_completion
from db import db_operations as db_ops
from db.db_operations import CodeSnapshot, CodeReviewSuggestion

CONFIDENCE_THRESHOLD = 0.6

VALID_LABELS = {CLASSIFICATION_ACCEPTED, CLASSIFICATION_MODIFIED, CLASSIFICATION_REJECTED}
DEFAULT_LABEL = CLASSIFICATION_REJECTED

DEFAULT_CATEGORY = "Other"
DEFAULT_RECURRING_ISSUE = "Other"
UNKNOWN_LABEL = "unknown"


def build_prompt(review: CodeReviewSuggestion, parent_code: str, child_code: str) -> str:
    """
    Builds a structured prompt for the LLM to classify the review.
    :param review: Code review dict with 'suggestion', 'line_start', 'line_end'
    :param parent_code: Parent (BEFORE) code snapshot text
    :param child_code: Child (AFTER) code snapshot text
    :return: JSON-based prompt string
    """

    parent_lines = parent_code.splitlines()
    child_lines = child_code.splitlines()
    total_lines = max(len(parent_lines), len(child_lines))

    # Use defaults if missing
    start = review.line_start if review.line_start is not None else 1
    end = review.line_end if review.line_end is not None else total_lines

    parent_excerpt = "\n".join(parent_lines[max(0, start - 2):min(len(parent_lines), end + 2)])
    child_excerpt = "\n".join(child_lines[max(0, start - 2):min(len(child_lines), end + 2)])

    return f"""
        You are a precise code-review classifier.
        Task: Given a review comment and BEFORE/AFTER code snapshots:
        1) classify the review outcome as accepted, modified, or not_handled
        2) assign a category from the predefined list
        3) provide a short recurring_issue description for recurring developer issues (e.g., "missing type hints")
    
        Definitions:
        - accepted → the suggestion was fully implemented as written.
        - modified → the suggestion was implemented but with some variation, extension, or partial change.
        - rejected → the suggestion was ignored, rejected, or missing from the updated code.
    
        Predefined categories: {', '.join(REVIEW_CATEGORIES)}
    
        Return a JSON object with fields:
        - label (one of: accepted, modified, rejected)
        - confidence (0-1)
        - category (one of the predefined categories above)
        - recurring_issue (short description, e.g., "missing type hints")
        - rationale (short, 1-2 sentences)
    
        ----
        Review comment:
        \"\"\"{review.suggestion}\"\"\"
    
        Parent (BEFORE) code (lines {start}-{end} and small context):
        \"\"\"{parent_excerpt}\"\"\"
    
        Child (AFTER) code (same context):
        \"\"\"{child_excerpt}\"\"\"
    
        Return ONLY the JSON object.
        Do NOT include ```json fences or explanations.
        """


def llm_classify_review(review: CodeReviewSuggestion, parent_snapshot: CodeSnapshot, child_snapshot: CodeSnapshot) -> \
        Tuple[str, float, str, str, str]:
    """
    Uses LLM to classify a code review suggestion between parent and child snapshots.
    Returns classification details, falling back to defaults if parsing fails or confidence is low.

    :param review: CodeReviewSuggestion object
    :param parent_snapshot: CodeSnapshot object representing the parent (BEFORE)
    :param child_snapshot: CodeSnapshot object representing the child (AFTER)
    :return: Tuple(classification label, confidence, rationale, category, recurring_issue)
    """

    prompt = build_prompt(review, parent_snapshot.code_text, child_snapshot.code_text)
    raw_output = get_llm_completion(prompt)

    # Parse JSON response
    try:
        parsed = json.loads(raw_output)
        label = parsed.get("label", "").strip().lower()
        confidence = float(parsed.get("confidence", 0.0))
        rationale = parsed.get("rationale", "")
        category = parsed.get("category", "").strip()
        recurring_issue = parsed.get("recurring_issue", "").strip()
    except Exception as e:
        return (
            DEFAULT_LABEL,
            0.0,
            f"Failed to parse model response: {raw_output[:200]} | error={e}",
            DEFAULT_CATEGORY,
            DEFAULT_RECURRING_ISSUE,
        )

    # Confidence check
    if confidence < CONFIDENCE_THRESHOLD:
        return (
            DEFAULT_LABEL,
            confidence,
            f"Low confidence ({confidence:.2f}), queued for manual verification. Rationale: {rationale}",
            category or DEFAULT_CATEGORY,
            recurring_issue or DEFAULT_RECURRING_ISSUE,
        )

    # Ensure valid label/category
    if label not in VALID_LABELS:
        label = DEFAULT_LABEL
    if category not in REVIEW_CATEGORIES:
        category = DEFAULT_CATEGORY
    if not recurring_issue:
        recurring_issue = DEFAULT_RECURRING_ISSUE

    return label, confidence, rationale, category, recurring_issue


def classify_commits(db: Session, merged_commit_id: str):
    """
    Walks the commit chain starting from the merged commit, traversing back through
    parent commits, and classifies reviews for each parent-child pair.

    :param db: Active database session
    :param merged_commit_id: The final merged commit to analyze
    :return: List of classification results across the commit chain
    """
    current_snapshot: CodeSnapshot = db_ops.get_snapshot_by_commit(db, merged_commit_id)
    if current_snapshot is None:
        raise ValueError(f"Commit {merged_commit_id} not found in snapshots.")

    all_classifications: List[Dict] = []

    # Traverse the chain backwards until root (parent_commit_id = None)
    while current_snapshot.parent_commit_id:
        parent_snapshot: CodeSnapshot = db_ops.get_snapshot_by_commit(db, current_snapshot.parent_commit_id)
        if parent_snapshot is None:
            raise ValueError(f"Parent commit {current_snapshot.parent_commit_id} not found in snapshots.")

        parent_reviews: List[CodeReviewSuggestion] = db_ops.get_reviews_for_commit(db, parent_snapshot.commit_id)
        if not parent_reviews:
            print(f"No reviews recorded for parent commit {parent_snapshot.commit_id}")
            current_snapshot = parent_snapshot
            continue

        # Classify each review
        for review in parent_reviews:
            try:
                label, confidence, rationale, category, recurring_issue = llm_classify_review(
                    review, parent_snapshot, current_snapshot
                )
                print(f"LLM classified review {review.review_id} -> {label} (conf={confidence})")
            except Exception as e:
                print(f"LLM classification failed for review {review.review_id}: {e}")
                label, confidence, rationale, category, recurring_issue = (
                    UNKNOWN_LABEL,
                    0.0,
                    f"Error, queued for manual verification {str(e)}",
                    DEFAULT_CATEGORY,
                    DEFAULT_RECURRING_ISSUE,
                )

            all_classifications.append({
                "review_id": review.review_id,
                "parent_commit_id": parent_snapshot.commit_id,
                "child_commit_id": current_snapshot.commit_id,
                "classification": label,
                "confidence": float(confidence),
                "rationale": rationale,
                "category": category or DEFAULT_CATEGORY,
                "recurring_issue": recurring_issue or DEFAULT_RECURRING_ISSUE,
            })

        # Move up the chain
        current_snapshot = parent_snapshot

    return all_classifications
