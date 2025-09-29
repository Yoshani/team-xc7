"""
prod_metrics/classify_reviews.py

Behavior:
    - Attempts to call a remote LLM to classify reviews.
"""

import json
import os
from typing import Dict, List, Tuple, Optional

from groq import Groq

# ---------- CONFIG ----------
DB_DIR = "/Users/yoshani/PycharmProjects/TDPProj/db/"
SNAPSHOTS_FILE = os.path.join(DB_DIR, "code_snapshots.json")
REVIEWS_FILE = os.path.join(DB_DIR, "code_review_suggestions.json")

CATEGORIES = ["Code Quality", "Documentation", "Debugging", "Performance", "Security", "Style", "Other"]


# ---------- Utilities ----------
def load_json_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_snapshot_by_commit(snapshots: List[Dict], commit_id: str) -> Optional[Dict]:
    for s in snapshots:
        if s["commit_id"] == commit_id:
            return s
    return None


def get_reviews_for_commit(reviews: List[Dict], commit_id: str) -> List[Dict]:
    return [r for r in reviews if r["commit_id"] == commit_id]


def split_lines(code_text: str) -> List[str]:
    # keep newline semantics consistent; line numbers are 1-based
    return code_text.split("\n")


def build_prompt(review, parent_code, child_code):
    """
    Builds a structured prompt for the LLM to classify the review.
    :param review: Code review dict with 'suggestion', 'line_start', 'line_end'
    :param parent_code: Parent (BEFORE) code snapshot text
    :param child_code: Child (AFTER) code snapshot text
    :return: JSON-based prompt string
    """
    start, end = review.get("line_start", 1), review.get("line_end", 1)
    parent_lines = parent_code.splitlines()
    child_lines = child_code.splitlines()

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
        - not_handled → the suggestion was ignored, rejected, or missing from the updated code.
    
        Predefined categories: {', '.join(CATEGORIES)}
    
        Return a JSON object with fields:
        - label (one of: accepted, modified, not_handled)
        - confidence (0-1)
        - category (one of the predefined categories above)
        - recurring_issue (short description, e.g., "missing type hints")
        - rationale (short, 1-2 sentences)
    
        ----
        Review comment:
        \"\"\"{review.get('suggestion')}\"\"\"
    
        Parent (BEFORE) code (lines {start}-{end} and small context):
        \"\"\"{parent_excerpt}\"\"\"
    
        Child (AFTER) code (same context):
        \"\"\"{child_excerpt}\"\"\"
    
        Return ONLY the JSON object.
        Do NOT include ```json fences or explanations.
        """


# ---------- LLM-based classifier ----------
def llm_classify_review(review: Dict, parent_snapshot: Dict, child_snapshot: Dict, client) -> Tuple[
    str, float, str, str, str]:
    """
    Uses Groq LLM (openai/gpt-oss-20b) to classify review.
    Falls back to 'unknown' if confidence < 0.6 or JSON parsing fails.
    Returns label, confidence (0-1), rationale text.
    """

    # Build structured prompt
    prompt = build_prompt(review, parent_snapshot["code_text"], child_snapshot["code_text"])

    # Call Groq model
    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_completion_tokens=512,
        top_p=1,
        reasoning_effort="medium",
        stream=False
    )

    raw_output = completion.choices[0].message.content.strip()

    # Parse JSON response
    try:
        parsed = json.loads(raw_output)
        label = parsed.get("label", "").strip().lower()
        confidence = float(parsed.get("confidence", 0.0))
        rationale = parsed.get("rationale", "")
        category = parsed.get("category", "").strip()
        recurring_issue = parsed.get("recurring_issue", "").strip()
    except Exception as e:
        return ("unknown", 0.0,
                f"Failed to parse model response: {raw_output[:200]} | error={e}",
                "Other", "Other")

    # Confidence check
    if confidence < 0.6:
        return ("unknown", confidence,
                f"Low confidence ({confidence:.2f}), queued for manual verification. Rationale: {rationale}",
                category or "Other",
                recurring_issue or "Other")

    # Ensure valid label/category
    if label not in ("accepted", "modified", "not_handled"):
        label = "not_handled"
    if category not in CATEGORIES:
        category = "Other"
    if not recurring_issue:
        recurring_issue = "Other"

    return label, confidence, rationale, category, recurring_issue


# ---------- Main classification function ----------
def classify_parent_reviews(merged_commit_id: str):
    """
    Given a merged commit id (child), find parent, load relevant reviews,
    and classify each review as accepted/modified/rejected/not_handled.
    """
    # load data
    snapshots = load_json_file(SNAPSHOTS_FILE)
    reviews = load_json_file(REVIEWS_FILE)

    child_snap = find_snapshot_by_commit(snapshots, merged_commit_id)
    if child_snap is None:
        raise ValueError(f"Child commit {merged_commit_id} not found in snapshots.")

    parent_id = child_snap.get("parent_commit_id")
    if not parent_id:
        raise ValueError(f"Child commit {merged_commit_id} has no parent_commit_id (cannot compare).")

    parent_snap = find_snapshot_by_commit(snapshots, parent_id)
    if parent_snap is None:
        raise ValueError(f"Parent commit {parent_id} not found in snapshots.")

    parent_reviews = get_reviews_for_commit(reviews, parent_id)
    if not parent_reviews:
        print(f"No reviews recorded for parent commit {parent_id}")
        return []

    client = Groq(api_key="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")
    results = []

    for review in parent_reviews:
        try:
            label, conf, rationale, category, recurring_issue = llm_classify_review(review, parent_snap, child_snap, client)
            print(f"LLM classified review {review['review_id']} -> {label} (conf={conf})")
        except Exception as e:
            print(f"LLM classification failed for review {review['review_id']}: {e}")
            label, conf, rationale, category, recurring_issue = "not_handled", 0.0, str(e), "Other", "Other"

        results.append({
            "review_id": review["review_id"],
            "parent_commit_id": parent_id,
            "child_commit_id": merged_commit_id,
            "classification": label,
            "confidence": float(conf),
            "rationale": rationale,
            "category": category,
            "recurring_issue": recurring_issue
        })

    return results


# ---------- CLI ----------
if __name__ == "__main__":

    res = classify_parent_reviews("22222222-2222-2222-2222-222222222222")
    print("\nClassification results:")
    for result in res:
        print(json.dumps(result, indent=2))
