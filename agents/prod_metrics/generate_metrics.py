"""
prod_metrics/generate_metrics.py

Behavior:
    - Generates productivity metrics based on classified code reviews.
"""
import json
import time

from sqlalchemy.orm import Session

from agents.prod_metrics.constants import CLASSIFICATION_ACCEPTED, CLASSIFICATION_MODIFIED, CLASSIFICATION_REJECTED
from agents.prod_metrics.llm_agent import get_llm_completion
from db import db_operations as db_ops
from util.helper import safe_json_parse

RECURRING_ISSUE_TOP_K = 5
MAX_RETRIES = 3
RETRY_DELAY = 2


def build_recurring_issue_prompt(issues: list[str]) -> str:
    """
    Builds a structured prompt for the LLM to group recurring issues into canonical categories.
    :param issues: List of issue strings (raw descriptions from LLM classifications)
    :return: JSON-based prompt string
    """
    return f"""
    You are an assistant that groups recurring developer issues into canonical categories.

    Task:
    - Given a list of recurring issues, map each issue to a canonical category.
    - Issues with similar meaning should be grouped together, even if worded differently.
    - Use short, descriptive canonical names (e.g., "print statements in production", "missing type hints").
    - If an issue doesn’t fit any existing group, create a new category.

    Input issues:
    {json.dumps(issues, indent=2)}

    Return ONLY a JSON object with format:
    {{
      "canonical_categories": {{
        "<canonical_category>": [
          "<original issue 1>",
          "<original issue 2>"
        ]
      }}
    }}

    Do NOT include explanations or markdown fences. Return only valid JSON. Do not include explanations or code fences.”
    """


def llm_group_recurring_issues(issues: list[str]) -> dict:
    """
    Uses an LLM to group recurring issues into canonical categories.
    Automatically retries on empty or invalid responses.
    :param issues: List of raw recurring issue strings
    :return: dict mapping canonical_category -> list of original issues
    """
    if not issues:
        return {}

    issues_to_send = list(set(issues))
    prompt = build_recurring_issue_prompt(issues_to_send)
    attempt = 0

    while attempt < MAX_RETRIES:
        attempt += 1
        raw_output = get_llm_completion(prompt)

        if not raw_output or not raw_output.strip():
            print(f"[Attempt {attempt}] Empty LLM response — retrying...")
            time.sleep(RETRY_DELAY)
            continue

        parsed = safe_json_parse(raw_output)

        if parsed and isinstance(parsed, dict) and "canonical_categories" in parsed:
            return parsed.get("canonical_categories", {})

        print(f"[Attempt {attempt}] Failed to parse LLM output: {raw_output[:200]}")
        time.sleep(RETRY_DELAY)

    # Final fallback — no valid output after retries
    print("LLM failed to produce valid grouped issues after multiple retries.")
    return {"LLMError": ["Failed to generate valid grouped issues. Please retry later."]}


from collections import defaultdict, Counter


def batched_llm_grouped_recurring_issues(issues: list[str]) -> dict:
    """
    Groups recurring issues using LLM in batches to handle large inputs.
    :param issues: Set of raw recurring issue strings
    :return: Dict mapping canonical_category -> list of original issues
    """
    BATCH_SIZE = 5
    all_grouped = {}

    for i in range(0, len(issues), BATCH_SIZE):
        batch = issues[i:i + BATCH_SIZE]
        grouped = llm_group_recurring_issues(batch)
        # Merge into all_grouped
        for cat, originals in grouped.items():
            all_grouped.setdefault(cat, []).extend(originals)
    return all_grouped


def calculate_metrics(db: Session) -> tuple[dict, dict, dict, dict, float, float, dict, dict]:
    """
    Calculate productivity metrics based on classified code reviews.
    :param db: Database session
    :return : Tuple containing:
        - avg_per_dev: Average suggestions handled per developer per day
        - acceptance_rate: Acceptance rate (accepted + modified) per developer
        - per_dev_category: Suggestions handled per developer by category
        - grouped_issues: Top 5 recurring issues grouped by developer
    """
    classifications = db_ops.get_all_classifications_with_snapshot_info(db)

    # developer-level counters
    handled_by_dev_day = defaultdict(lambda: defaultdict(int))
    dev_totals = defaultdict(int)
    accepted_or_modified = defaultdict(int)
    rejected = defaultdict(int)
    category_counts = defaultdict(lambda: defaultdict(lambda: {CLASSIFICATION_ACCEPTED: 0, CLASSIFICATION_REJECTED: 0}))
    raw_issues_by_dev = defaultdict(list)

    # team-level counters
    handled_by_team_day = defaultdict(int)
    team_total = 0
    team_accepted_or_modified = 0
    team_category_counts = defaultdict(lambda: {CLASSIFICATION_ACCEPTED: 0, CLASSIFICATION_REJECTED: 0})

    for classification, dev_name, snapshot_date in classifications:
        dev_totals[dev_name] += 1
        classification_type = classification.classification
        category = classification.category or "Other"
        totals_day = snapshot_date.date() if snapshot_date else None

        if classification_type in (CLASSIFICATION_ACCEPTED, CLASSIFICATION_MODIFIED):
            if totals_day:
                handled_by_dev_day[dev_name][totals_day] += 1
                handled_by_team_day[totals_day] += 1
            accepted_or_modified[dev_name] += 1
            team_accepted_or_modified += 1
            category_counts[dev_name][category][CLASSIFICATION_ACCEPTED] += 1
            team_category_counts[category][CLASSIFICATION_ACCEPTED] += 1
        elif classification_type == CLASSIFICATION_REJECTED:
            rejected[dev_name] += 1
            category_counts[dev_name][category][CLASSIFICATION_REJECTED] += 1
            team_category_counts[category][CLASSIFICATION_REJECTED] += 1

        if classification.recurring_issue and classification.recurring_issue != "Other":
            raw_issues_by_dev[dev_name].append(classification.recurring_issue)

        # team totals
        team_total += 1

    all_issues = [issue for issues in raw_issues_by_dev.values() for issue in issues]
    global_grouped = batched_llm_grouped_recurring_issues(all_issues)

    # --- DEV LEVEL ---
    acceptance_rate, avg_per_dev, grouped_issues, per_dev_category = calculate_developer_metrics(
        accepted_or_modified, category_counts, dev_totals, handled_by_dev_day, raw_issues_by_dev, global_grouped)

    # --- TEAM LEVEL ---
    team_acceptance_rate, team_avg_handled, team_category_counts_final, team_grouped_issues = calculate_team_metrics(
        handled_by_team_day, global_grouped, team_accepted_or_modified, team_category_counts, team_total)

    return (avg_per_dev,
            acceptance_rate,
            per_dev_category,
            grouped_issues,
            team_avg_handled,
            team_acceptance_rate,
            team_category_counts_final,
            team_grouped_issues)


def calculate_team_metrics(handled_by_team_day, global_grouped, team_accepted_or_modified,
                           team_category_counts,
                           team_total):
    """
    Calculate team-level productivity metrics.
    :param handled_by_team_day: Handled suggestions by team per day
    :param global_grouped: Global grouped recurring issues from LLM
    :param team_accepted_or_modified: Accepted or modified suggestions at the team level
    :param team_category_counts: Team category counts
    :param team_total: Total suggestions at the team level
    :return: Tuple containing:
        - team_acceptance_rate: Overall acceptance rate (accepted + modified) for the team
        - team_avg_handled: Average suggestions handled by the team per day
        - team_category_counts_final: Suggestions handled by the team by category
        - team_grouped_issues: Top 5 recurring issues grouped at the team level
    """
    # team avg handled
    team_avg_handled = sum(handled_by_team_day.values()) / len(handled_by_team_day) if handled_by_team_day else 0.0
    team_avg_handled = round(team_avg_handled, 2)

    # team acceptance rate
    team_acceptance_rate = (team_accepted_or_modified / team_total) if team_total else 0.0
    team_acceptance_rate = round(team_acceptance_rate, 2)

    # team per category
    team_category_counts_final = {cat: vals[CLASSIFICATION_ACCEPTED] + vals[CLASSIFICATION_REJECTED]
                                  for cat, vals in team_category_counts.items()}
    # team recurring issues
    team_grouped_issues = {
        canonical: len(instances)
        for canonical, instances in global_grouped.items()
    }
    team_grouped_issues = dict(Counter(team_grouped_issues).most_common(RECURRING_ISSUE_TOP_K))

    return team_acceptance_rate, team_avg_handled, team_category_counts_final, team_grouped_issues


def calculate_developer_metrics(accepted_or_modified, category_counts, dev_totals, handled_by_dev_day,
                                raw_issues_by_dev, global_grouped):
    """
    Calculate developer-level productivity metrics.
    :param accepted_or_modified: Accepted or modified suggestions per developer
    :param category_counts: Category counts per developer
    :param dev_totals: Total suggestions per developer
    :param handled_by_dev_day: Handled suggestions by developer per day
    :param raw_issues_by_dev: Recurring issues per developer
    :param global_grouped: Global grouped recurring issues from LLM
    :return: Tuple containing:
        - acceptance_rate: Acceptance rate (accepted + modified) per developer
        - avg_per_dev: Average suggestions handled per developer per day
        - grouped_issues: Top 5 recurring issues grouped by developer
        - per_dev_category: Suggestions handled per developer by category
    """
    # averages
    avg_per_dev = {}
    for dev, by_day in handled_by_dev_day.items():
        avg = sum(by_day.values()) / len(by_day) if by_day else 0.0
        avg_per_dev[dev] = round(avg, 2)

    # acceptance rate (inclusive of both accepted and modified)
    acceptance_rate = {
        dev: round((accepted_or_modified.get(dev, 0) / dev_totals[dev]), 2) if dev_totals[dev] else 0.0
        for dev in dev_totals
    }

    # suggestions per dev by category
    per_dev_category = {
        dev: {cat: (vals[CLASSIFICATION_ACCEPTED] + vals[CLASSIFICATION_REJECTED]) for cat, vals in cats.items()} for
        dev, cats in
        category_counts.items()}

    # group recurring issues per dev with LLM
    grouped_issues = {}
    for dev, issues in raw_issues_by_dev.items():
        dev_counts = {}
        for canonical, originals in global_grouped.items():
            count = sum(1 for issue in issues if issue in originals)
            if count > 0:
                dev_counts[canonical] = count
        grouped_issues[dev] = dict(Counter(dev_counts).most_common(RECURRING_ISSUE_TOP_K))

    return acceptance_rate, avg_per_dev, grouped_issues, per_dev_category
