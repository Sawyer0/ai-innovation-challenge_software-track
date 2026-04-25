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


# Pell Grant proration tiers per federal student aid rules (34 CFR 690.63)
_PELL_TIERS = [
    (12, 1.00),  # full-time:           100%
    (9,  0.75),  # three-quarter-time:   75%
    (6,  0.50),  # half-time:            50%
    (1,  0.25),  # less-than-half-time:  25%
]
_PELL_AID_TYPES = {"pell", "both"}


def calculate_pell_proration(
    financial_aid_type: Optional[str],
    planned_credits: float,
) -> Optional[dict]:
    """
    Return Pell proration info for display when a student receives Pell.

    Returns None when the student does not receive Pell.
    Otherwise returns:
      {
        "planned_credits": float,
        "percentage": float,        # 0.25 / 0.50 / 0.75 / 1.00
        "percentage_display": str,  # "75%"
        "enrollment_tier": str,     # "three-quarter-time"
        "note": str,                # plain-English explanation
      }
    """
    if not financial_aid_type or financial_aid_type.lower() not in _PELL_AID_TYPES:
        return None

    tier_labels = {
        1.00: ("full-time",             "full Pell award"),
        0.75: ("three-quarter-time",    "75% of your Pell award"),
        0.50: ("half-time",             "50% of your Pell award"),
        0.25: ("less-than-half-time",   "25% of your Pell award"),
    }

    percentage = 0.0
    for min_credits, pct in _PELL_TIERS:
        if planned_credits >= min_credits:
            percentage = pct
            break

    label, award_desc = tier_labels.get(percentage, ("less-than-half-time", "25% of your Pell award"))

    _next_tier = {0.25: (6, "50%"), 0.50: (9, "75%"), 0.75: (12, "100%")}

    if percentage == 1.00:
        note = f"At {planned_credits} credits (full-time) you receive your full Pell award."
    elif percentage > 0:
        next_credits, next_pct = _next_tier[percentage]
        note = (
            f"At {planned_credits} credits ({label}) you receive {award_desc}. "
            f"Add courses to reach {next_credits}+ credits and unlock {next_pct} of your award."
        )
    else:
        note = (
            f"At {planned_credits} credits you are below the minimum for any Pell disbursement (6 credits). "
            "You will not receive a Pell award this semester."
        )

    return {
        "planned_credits": planned_credits,
        "percentage": percentage,
        "percentage_display": f"{int(percentage * 100)}%",
        "enrollment_tier": label,
        "note": note,
    }


_TAP_AID_TYPES = {"tap", "both"}


def check_tap_elective_compliance(
    financial_aid_type: Optional[str],
    program_code: Optional[str],
    recommended_courses: list,
    db: Session,
) -> list:
    """
    For TAP recipients, flag any recommended elective not listed in the
    program's allowable elective groups (ProgramRequirement rows where
    is_required=False).

    Returns the same list with compliance_status and compliance_note
    updated in-place for any non-allowable electives.

    Non-TAP students and required courses are untouched.
    """
    if not financial_aid_type or financial_aid_type.lower() not in _TAP_AID_TYPES:
        return recommended_courses

    if not program_code:
        return recommended_courses

    # Load all allowable elective codes for this program from the DB
    allowable_rows = (
        db.query(models.ProgramRequirement)
        .join(models.Program, models.Program.id == models.ProgramRequirement.program_id)
        .filter(
            models.Program.program_code == program_code,
            models.ProgramRequirement.is_required == False,  # noqa: E712
        )
        .all()
    )
    allowable_codes = {row.course_code for row in allowable_rows if row.course_code}

    # Also load required course codes so we can skip them
    required_rows = (
        db.query(models.ProgramRequirement)
        .join(models.Program, models.Program.id == models.ProgramRequirement.program_id)
        .filter(
            models.Program.program_code == program_code,
            models.ProgramRequirement.is_required == True,  # noqa: E712
        )
        .all()
    )
    required_codes = {row.course_code for row in required_rows if row.course_code}

    for course in recommended_courses:
        code = course.get("course_code") if isinstance(course, dict) else getattr(course, "course_code", None)
        if not code:
            continue

        # Required courses are always TAP-allowable — only check electives
        if code in required_codes:
            continue

        # If it's an elective and NOT in the allowable list, flag it
        if code not in allowable_codes:
            if isinstance(course, dict):
                course["compliance_status"] = "warning"
                course["compliance_note"] = (
                    f"{code} does not appear in the TAP-allowable elective list for {program_code}. "
                    "Taking this course may not count toward your TAP-eligible credits. "
                    "Confirm with your financial aid advisor before registering."
                )
            else:
                course.compliance_status = "warning"
                course.compliance_note = (
                    f"{code} does not appear in the TAP-allowable elective list for {program_code}. "
                    "Taking this course may not count toward your TAP-eligible credits. "
                    "Confirm with your financial aid advisor before registering."
                )

    return recommended_courses


_ONLINE_MODES = {"online", "hybrid"}
_F1_MIN_CREDITS = 12
_F1_MAX_ONLINE_COURSES = 1


def check_visa_compliance(
    student_type: Optional[str],
    planned_credits: float,
    planned_course_codes: list,
    db: Session,
) -> Tuple[bool, Optional[str]]:
    """
    Enforce F-1 visa rules for international students (deterministic, pre-AI).

    Rules per USCIS / ICE regulations:
      - Must carry ≥12 credits (full-time)
      - May count at most 1 online/hybrid course toward the full-time requirement
    Returns (is_compliant, violation_message).
    """
    if not student_type or student_type.lower() != "international":
        return True, None

    violations = []

    if planned_credits < _F1_MIN_CREDITS:
        violations.append(
            f"F-1 visa requires full-time enrollment of at least {_F1_MIN_CREDITS} credits. "
            f"Your current plan has {planned_credits} credits. "
            f"Dropping below {_F1_MIN_CREDITS} credits may result in visa status violation. "
            "Please add more courses or speak with the International Student Office before registering."
        )

    if planned_course_codes:
        online_courses = (
            db.query(models.Course)
            .filter(
                models.Course.code.in_(planned_course_codes),
                models.Course.instruction_mode.isnot(None),
            )
            .all()
        )
        online_count = sum(
            1 for c in online_courses
            if c.instruction_mode and c.instruction_mode.lower() in _ONLINE_MODES
        )
        if online_count > _F1_MAX_ONLINE_COURSES:
            violations.append(
                f"F-1 visa regulations allow at most {_F1_MAX_ONLINE_COURSES} online or hybrid course "
                f"per semester to count toward full-time status. "
                f"Your current plan includes {online_count} online/hybrid courses. "
                "Please replace the extra online courses with in-person sections."
            )

    if violations:
        return False, " | ".join(violations)

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
