"""
Utility functions for the BMCC backend.
"""

from .academic_utils import (
    get_next_semester,
    calculate_remaining_credits,
    get_current_academic_year,
)

__all__ = [
    "get_next_semester",
    "calculate_remaining_credits",
    "get_current_academic_year",
]
