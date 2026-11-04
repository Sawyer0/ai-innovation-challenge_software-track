"""Helpers for turning an LLM's text reply into JSON."""

import json
from typing import Any


def strip_code_fences(text: str) -> str:
    """Remove the ```json ... ``` fence models often wrap around JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def parse_json_response(text: str) -> Any:
    """Parse a model reply as JSON, tolerating code fences. Raises ValueError on bad JSON."""
    return json.loads(strip_code_fences(text))


def safe_json_parse(text: str, default: Any = None) -> Any:
    """Like parse_json_response, but return ``default`` instead of raising."""
    try:
        return parse_json_response(text)
    except json.JSONDecodeError:
        return default
