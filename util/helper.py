import json
import re


def safe_json_parse(raw_output: str) -> dict:
    """
    Safely parse potentially malformed or truncated JSON from LLM output.
    :param raw_output: Raw text output from the LLM
    :return: Parsed dict or fallback empty structure
    """
    if not raw_output or not raw_output.strip():
        return {}

    # Remove Markdown code fences (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_output.strip(), flags=re.DOTALL)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # If it still fails, try a last-resort fix for minor formatting issues
        try:
            # Remove trailing commas, fix unescaped newlines, etc.
            fixed = re.sub(r",\s*([\]}])", r"\1", cleaned)
            return json.loads(fixed)
        except Exception:
            return {}
