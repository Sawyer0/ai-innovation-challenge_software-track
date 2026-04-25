"""
Utility functions for the BMCC backend.
"""

from .academic_utils import (
    get_next_semester,
    calculate_remaining_credits,
    get_current_academic_year,
    check_financial_aid_compliance,
    check_visa_compliance,
    calculate_pell_proration,
    check_tap_elective_compliance,
)
from .ai_helpers import (
    clean_json_response,
    safe_json_parse,
    format_list_for_prompt,
    format_dict_for_prompt,
    truncate_for_prompt,
)
from .ai_helpers import (
    clean_json_response,
    safe_json_parse,
    format_list_for_prompt,
    format_dict_for_prompt,
    truncate_for_prompt,
)

__all__ = [
    "get_next_semester",
    "calculate_remaining_credits",
    "get_current_academic_year",
    "clean_json_response",
    "safe_json_parse",
    "format_list_for_prompt",
    "format_dict_for_prompt",
    "truncate_for_prompt",
]
