"""Deterministic compliance guardrails: financial aid, F-1 visa, Pell proration, TAP electives.

These rules run before (and after) the AI and are never delegated to it.
"""

from sqlalchemy.orm import Session

from .. import models


def calculate_remaining_credits(
    enrollment_status: str | None, current_planned_credits: float, db: Session
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
    rule = (
        db.query(models.EnrollmentStatusRule)
        .filter(models.EnrollmentStatusRule.status_name == enrollment_status)
        .first()
    )

    # Unknown status or no cap configured: fall back to the full-time maximum.
    max_credits = float(rule.max_credits) if rule and rule.max_credits else 18.0

    remaining = max_credits - current_planned_credits
    return max(0, remaining)  # Don't return negative


_AID_LABELS = {
    "pell": "the Pell Grant",
    "tap": "TAP",
    "both": "Pell and TAP",
    "excelsior": "the Excelsior Scholarship",
    "loans": "federal student loans",
}


def _format_credits(credits: float) -> str:
    return f"{credits:g}"


def check_financial_aid_compliance(
    financial_aid_type: str | None,
    planned_credits: float,
    enrollment_status: str | None,
    db: Session,
    *,
    allow_empty_plan: bool = True,
) -> tuple[bool, str | None]:
    """
    Check if a student's planned enrollment meets the minimum credits of their aid.

    The minimum comes from the FinancialAidConstraint row for the aid type
    (data/rules.json). Constraints with block_underload=False only advise, so they
    never fail the check.

    Args:
        financial_aid_type: Type of aid (pell, tap, both, ...) or None
        planned_credits: Total credits planned for the semester
        enrollment_status: Current enrollment status
        db: Database session
        allow_empty_plan: When True, a plan with 0 credits passes. That is the
            pre-AI case, where the student has not planned anything yet. Pass
            False to check a finished plan, where 0 credits is a shortfall.

    Returns:
        Tuple of (is_compliant, violation_message)
    """
    if not financial_aid_type:
        return True, None

    aid_type = financial_aid_type.strip().lower()
    constraint = (
        db.query(models.FinancialAidConstraint)
        .filter(models.FinancialAidConstraint.aid_type == aid_type)
        .first()
    )

    if not constraint or not constraint.min_credits_required:
        return True, None

    if constraint.block_underload is False:
        return True, None

    min_credits = float(constraint.min_credits_required)
    if planned_credits == 0 and allow_empty_plan:
        return True, None

    if planned_credits < min_credits:
        label = _AID_LABELS.get(aid_type, aid_type.upper())
        message = (
            f"This plan has {_format_credits(planned_credits)} credits, but {label} "
            f"requires at least {_format_credits(min_credits)} credits per semester."
        )
        if constraint.warning_message:
            message = f"{message} {constraint.warning_message}"
        return False, message

    return True, None


# Pell Grant proration tiers per federal student aid rules (34 CFR 690.63)
_PELL_TIERS = [
    (12, 1.00),  # full-time:           100%
    (9, 0.75),  # three-quarter-time:   75%
    (6, 0.50),  # half-time:            50%
    (1, 0.25),  # less-than-half-time:  25%
]
_PELL_AID_TYPES = {"pell", "both"}


def calculate_pell_proration(
    financial_aid_type: str | None,
    planned_credits: float,
) -> dict | None:
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
        1.00: ("full-time", "full Pell award"),
        0.75: ("three-quarter-time", "75% of your Pell award"),
        0.50: ("half-time", "50% of your Pell award"),
        0.25: ("less-than-half-time", "25% of your Pell award"),
    }

    percentage = 0.0
    for min_credits, pct in _PELL_TIERS:
        if planned_credits >= min_credits:
            percentage = pct
            break

    label, award_desc = tier_labels.get(
        percentage, ("less-than-half-time", "25% of your Pell award")
    )

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
    financial_aid_type: str | None,
    program_code: str | None,
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
        code = (
            course.get("course_code")
            if isinstance(course, dict)
            else getattr(course, "course_code", None)
        )
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
    student_type: str | None,
    planned_credits: float,
    planned_course_codes: list,
    db: Session,
    *,
    allow_empty_plan: bool = True,
) -> tuple[bool, str | None]:
    """
    Enforce F-1 visa rules for international students (deterministic, pre-AI).

    Rules per USCIS / ICE regulations:
      - Must carry ≥12 credits (full-time)
      - May count at most 1 online/hybrid course toward the full-time requirement
    allow_empty_plan has the same meaning as in check_financial_aid_compliance.
    Returns (is_compliant, violation_message).
    """
    if not student_type or student_type.lower() != "international":
        return True, None

    violations = []

    # Before the AI runs, 0 planned credits just means nothing is planned yet.
    short = planned_credits < _F1_MIN_CREDITS and not (planned_credits == 0 and allow_empty_plan)
    if short:
        violations.append(
            f"F-1 visa requires full-time enrollment of at least {_F1_MIN_CREDITS} credits. "
            f"Your current plan has {_format_credits(planned_credits)} credits. "
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
            1
            for c in online_courses
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
