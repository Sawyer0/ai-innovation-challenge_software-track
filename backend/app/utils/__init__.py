"""
Utility functions for the BMCC backend.
"""

from .academic_utils import (
    calculate_pell_proration,
    calculate_remaining_credits,
    check_financial_aid_compliance,
    check_tap_elective_compliance,
    check_visa_compliance,
    get_current_academic_year,
    get_next_semester,
)
from .ai_helpers import (
    clean_json_response,
    format_dict_for_prompt,
    format_list_for_prompt,
    safe_json_parse,
    truncate_for_prompt,
)

__all__ = [
    "calculate_pell_proration",
    "calculate_remaining_credits",
    "check_financial_aid_compliance",
    "check_tap_elective_compliance",
    "check_visa_compliance",
    "clean_json_response",
    "format_dict_for_prompt",
    "format_list_for_prompt",
    "get_current_academic_year",
    "get_next_semester",
    "safe_json_parse",
    "truncate_for_prompt",
]
