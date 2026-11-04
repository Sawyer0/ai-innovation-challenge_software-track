"""
System prompts for AI interactions.

All prompts are centralized here to maintain consistency and enable easy updates.
"""

from .advisement import (
    ADVISEMENT_SYSTEM_PROMPT,
    ADVISEMENT_USER_PROMPT_TEMPLATE,
)
from .eligibility import (
    ELIGIBILITY_SYSTEM_PROMPT,
    ELIGIBILITY_USER_PROMPT_TEMPLATE,
)
from .transcript import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)

__all__ = [
    "ADVISEMENT_SYSTEM_PROMPT",
    "ADVISEMENT_USER_PROMPT_TEMPLATE",
    "ELIGIBILITY_SYSTEM_PROMPT",
    "ELIGIBILITY_USER_PROMPT_TEMPLATE",
    "TRANSCRIPT_PARSING_SYSTEM_PROMPT",
    "TRANSCRIPT_PARSING_USER_PROMPT",
]
