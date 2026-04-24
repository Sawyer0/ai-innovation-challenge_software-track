"""
Academic utility functions for semester calculations and enrollment logic.
"""

from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from .. import models


def get_current_academic_year() -> int:
    """Get the current academic year (e.g., 2024 for 2024-2025)."""
    now = datetime.now()
    # Academic year starts in Fall (September)
    if now.month >= 9:
        return now.year
    return now.year - 1


def get_next_semester() -> str:
    """
    Calculate the next academic semester based on current date.
    
    Academic calendar:
    - Fall: September - December
    - Winter (optional): January
    - Spring: January - May
    - Summer: May - August
    
    Returns:
        String like "Fall 2024" or "Spring 2025"
    """
    now = datetime.now()
    month = now.month
    year = now.year
    
    # Determine next semester based on current month
    if month in [9, 10, 11, 12]:  # Fall - next is Spring
        return f"Spring {year + 1}"
    elif month in [1, 2, 3, 4, 5]:  # Spring/Spring - next is Summer or Fall
        if month <= 3:  # Early Spring - next is Summer
            return f"Summer {year}"
        else:  # Late Spring - next is Fall
            return f"Fall {year}"
    else:  # Summer (May-August) - next is Fall
        return f"Fall {year}"


def get_current_semester() -> str:
    """Get the current academic semester."""
    now = datetime.now()
    month = now.month
    year = now.year
    
    if month in [9, 10, 11, 12]:
        return f"Fall {year}"
    elif month in [1, 2, 3, 4, 5]:
        return f"Spring {year}"
    else:
        return f"Summer {year}"


def parse_semester(semester_str: str) -> Tuple[str, int]:
    """
    Parse a semester string like 'Fall 2024' into (term, year).
    
    Args:
        semester_str: String like "Fall 2024" or "Spring 2025"
    
    Returns:
        Tuple of (term, year) like ("Fall", 2024)
    """
    parts = semester_str.split()
    term = parts[0]
    year = int(parts[1])
    return term, year


def calculate_remaining_credits(
    enrollment_status: str,
    current_planned_credits: float,
    db: Session
) -> float:
    """
    Calculate remaining credit capacity for a student based on enrollment status.
    
    Args:
        enrollment_status: Status like "full-time", "half-time", "part-time"
        current_planned_credits: Credits already planned for next semester
        db: Database session to query enrollment rules
    
    Returns:
        Remaining credit capacity (can be negative if over limit)
    """
    # Query enrollment status rule
    rule = db.query(models.EnrollmentStatusRule).filter(
        models.EnrollmentStatusRule.status_name == enrollment_status
    ).first()
    
    if not rule:
        # Default to full-time if status not found
        max_credits = 18.0
    else:
        max_credits = float(rule.max_credits) if rule.max_credits else 18.0
    
    remaining = max_credits - current_planned_credits
    return max(0, remaining)  # Don't return negative


def get_min_credits_for_status(enrollment_status: str, db: Session) -> float:
    """
    Get minimum credits required for an enrollment status.
    
    Args:
        enrollment_status: Status like "full-time", "half-time"
        db: Database session
    
    Returns:
        Minimum credits required
    """
    rule = db.query(models.EnrollmentStatusRule).filter(
        models.EnrollmentStatusRule.status_name == enrollment_status
    ).first()
    
    if not rule:
        return 12.0  # Default to full-time minimum
    
    return float(rule.min_credits)


def check_financial_aid_compliance(
    financial_aid_type: Optional[str],
    planned_credits: float,
    enrollment_status: str,
    db: Session
) -> Tuple[bool, Optional[str]]:
    """
    Check if a student's planned enrollment complies with financial aid requirements.
    
    Args:
        financial_aid_type: Type of aid (pell, tap, etc.) or None
        planned_credits: Total credits planned for semester
        enrollment_status: Current enrollment status
        db: Database session
    
    Returns:
        Tuple of (is_compliant, warning_message)
    """
    if not financial_aid_type:
        return True, None
    
    constraint = db.query(models.FinancialAidConstraint).filter(
        models.FinancialAidConstraint.aid_type == financial_aid_type
    ).first()
    
    if not constraint:
        return True, None
    
    min_credits = float(constraint.min_credits_required) if constraint.min_credits_required else 0
    
    if planned_credits < min_credits:
        return False, constraint.warning_message or f"Need {min_credits} credits for {financial_aid_type}"
    
    return True, None


def format_course_list_for_prompt(courses: list) -> str:
    """
    Format a list of courses for inclusion in an AI prompt.
    
    Args:
        courses: List of course dicts with 'code' and 'title' keys
    
    Returns:
        Formatted string like "- MAT 206: Precalculus\n- ENG 101: Composition"
    """
    if not courses:
        return "None"
    
    formatted = []
    for course in courses:
        code = course.get('code', 'Unknown')
        title = course.get('title', 'Unknown')
        formatted.append(f"- {code}: {title}")
    
    return "\n".join(formatted)
