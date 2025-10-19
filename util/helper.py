import json


def safe_json_parse(raw_output: str) -> dict:
    """
    Safely parse potentially malformed or truncated JSON from LLM output.
    :param raw_output: Raw text output from the LLM
    :return: Parsed dict or fallback empty structure
    """
    if not raw_output or not raw_output.strip():
        return {}

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        # Try repairing truncated or open-ended JSON
        fixed = raw_output.strip()
        if not fixed.endswith("}"):
            fixed += "}}"
        try:
            return json.loads(fixed)
        except Exception as e:
            print(f"Failed to parse LLM output: {e}")
            return {}
