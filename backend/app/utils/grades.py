"""
Grade utilities for prerequisite checking and validation.
"""

from typing import Dict

# Grade ranking for comparison (higher = better)
GRADE_RANK: Dict[str, int] = {
    "A+": 12,
    "A": 11,
    "A-": 10,
    "B+": 9,
    "B": 8,
    "B-": 7,
    "C+": 6,
    "C": 5,
    "C-": 4,
    "D+": 3,
    "D": 2,
    "D-": 1,
    "F": 0,
    "W": 0,
    "WU": 0,
    "WN": 0,
    "I": 0,
}


def normalize_grade(grade: str) -> str:
    """Normalize grade string to standard format."""
    if not grade:
        return ""
    grade = grade.strip().upper()
    # Handle common variations
    if grade in ["CR", "P", "PASS", "S"]:
        return "C"  # Pass/fail courses count as C for prerequisites
    return grade


def meets_minimum_grade(grade: str, minimum: str = "C") -> bool:
    """
    Check if a grade meets the minimum requirement.
    
    Args:
        grade: The student's grade (e.g., "B+", "C")
        minimum: The minimum required grade (default: "C")
        
    Returns:
        True if grade meets or exceeds minimum
        
    Examples:
        >>> meets_minimum_grade("B", "C")
        True
        >>> meets_minimum_grade("C-", "C")
        False
        >>> meets_minimum_grade("A", "C")
        True
    """
    if not grade:
        return False
        
    grade = normalize_grade(grade)
    minimum = normalize_grade(minimum)
    
    # Handle pass/fail special cases
    if grade in ["CR", "P", "PASS", "S"]:
        return True  # Passing grade meets any minimum
        
    # Get ranks (default to 0 if unknown)
    grade_rank = GRADE_RANK.get(grade, 0)
    min_rank = GRADE_RANK.get(minimum, 5)  # Default to C rank if unknown
    
    return grade_rank >= min_rank


def is_passing_grade(grade: str) -> bool:
    """Check if grade is considered passing (D- or better)."""
    if not grade:
        return False
    grade = normalize_grade(grade)
    return GRADE_RANK.get(grade, 0) >= GRADE_RANK.get("D-", 1)
