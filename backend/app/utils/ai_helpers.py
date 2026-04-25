"""
Utility functions for AI response handling.
"""

import json
from typing import Any, Optional


def clean_json_response(text: str) -> str:
    """
    Clean up AI response text to ensure it's valid JSON.

    Removes markdown code block markers (```json, ```) that AI models
    often include in their responses.

    Args:
        text: Raw response text from AI model

    Returns:
        Cleaned text ready for JSON parsing

    Example:
        >>> clean_json_response('```json\\n{"key": "value"}\\n```')
        '{"key": "value"}'
    """
    json_text = text.strip()

    # Remove markdown code block markers
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    elif json_text.startswith("```"):
        json_text = json_text[3:]

    if json_text.endswith("```"):
        json_text = json_text[:-3]

    return json_text.strip()


def safe_json_parse(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON from AI response text.

    Combines cleaning and parsing with a fallback default value.

    Args:
        text: Raw response text from AI model
        default: Value to return if parsing fails (default: None)

    Returns:
        Parsed JSON object or default value if parsing fails

    Example:
        >>> safe_json_parse('```json\\n[1, 2, 3]\\n```', default=[])
        [1, 2, 3]
        >>> safe_json_parse('invalid json', default=[])
        []
    """
    try:
        cleaned = clean_json_response(text)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return default


def format_list_for_prompt(items: list, bullet: str = "-") -> str:
    """
    Format a list of items for inclusion in an AI prompt.

    Args:
        items: List of items to format
        bullet: Bullet character to use (default: "-")

    Returns:
        Formatted string with one item per line

    Example:
        >>> format_list_for_prompt(["apple", "banana"])
        '- apple\n- banana'
    """
    if not items:
        return "None"

    return "\n".join(f"{bullet} {item}" for item in items)


def format_dict_for_prompt(data: dict, separator: str = ": ") -> str:
    """
    Format a dictionary for inclusion in an AI prompt.

    Args:
        data: Dictionary to format
        separator: Separator between key and value

    Returns:
        Formatted string with one key-value pair per line

    Example:
        >>> format_dict_for_prompt({"name": "John", "age": 30})
        'name: John\nage: 30'
    """
    if not data:
        return "None"

    return "\n".join(f"{key}{separator}{value}" for key, value in data.items())


def truncate_for_prompt(text: str, max_chars: int = 2000, suffix: str = "...") -> str:
    """
    Truncate text to fit within prompt token limits.

    Args:
        text: Text to truncate
        max_chars: Maximum character limit
        suffix: Suffix to append if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_chars:
        return text

    return text[: max_chars - len(suffix)] + suffix
