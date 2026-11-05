import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..academics import (
    calculate_pell_proration,
    check_financial_aid_compliance,
    check_tap_elective_compliance,
    check_visa_compliance,
)
from ..database import get_db
from ..dependencies import get_ai_service, get_current_session, get_prerequisite_service
from ..dependencies.rate_limit import ai_rate_limit, rate_limit
from ..infrastructure.ai import NoProviderConfiguredError
from ..services.ai_service import AdvisementGenerationError, AIService
from ..services.prerequisite_service import PrerequisiteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["advisement"])


def _use_catalog_credits(response: schemas.AdvisementResponse, db: Session) -> None:
    """Replace the AI's credit counts with the catalog's, so the checks see real numbers."""
    for course in response.recommended_courses:
        row = db.query(models.Course).filter(models.Course.code == course.course_code).first()
        if row is not None and row.credits:
            course.credits = float(row.credits)


def _plan_violations(
    profile: models.StudentProfile,
    response: schemas.AdvisementResponse,
    db: Session,
) -> dict | None:
    """Re-run the credit and visa guardrails on the plan the AI actually returned.

    The pre-AI checks only see courses the student already planned (often none),
    so a plan the AI under-fills has to be checked here. Returns the 422 detail
    for the first failing plan, or None when the plan complies.
    """
    _use_catalog_credits(response, db)
    credits = sum(c.credits for c in response.recommended_courses)
    codes = [c.course_code for c in response.recommended_courses]
    messages: list[str] = []

    aid_ok, aid_message = check_financial_aid_compliance(
        financial_aid_type=profile.financial_aid_type,
        planned_credits=credits,
        enrollment_status=profile.enrollment_status,
        db=db,
        allow_empty_plan=False,
    )
    if not aid_ok and aid_message:
        messages.append(aid_message)

    visa_ok, visa_message = check_visa_compliance(
        student_type=profile.student_type,
        planned_credits=credits,
        planned_course_codes=codes,
        db=db,
        allow_empty_plan=False,
    )
    if not visa_ok and visa_message:
        messages.append(visa_message)

    if not messages:
        return None
    return {
        "type": "compliance_violation" if not aid_ok else "visa_compliance_violation",
        "stage": "plan",
        "aid_type": profile.financial_aid_type,
        "student_type": profile.student_type,
        "planned_credits": credits,
        "message": " ".join(messages),
    }


def _satisfied_course_codes(session: models.StudentSession) -> list[str]:
    """Completed and in-progress courses both count toward prerequisites."""
    return sorted(
        {
            c.course_code
            for c in session.courses
            if c.course_code and c.status in ("completed", "in-progress")
        }
    )


@router.get("/{session_id}/advisement/eligible")
def get_eligible_courses(
    session: models.StudentSession = Depends(get_current_session),
    prereq_service: PrerequisiteService = Depends(get_prerequisite_service),
) -> dict[str, list[str]]:
    profile = session.profile
    if not profile or not profile.program_code:
        raise HTTPException(status_code=400, detail="Student profile or program code not set")

    eligible = prereq_service.get_eligible_courses(
        profile.program_code, _satisfied_course_codes(session)
    )
    return {"eligible_courses": eligible}


@router.post("/{session_id}/advisement", response_model=schemas.AdvisementResponse)
async def advisement(
    chat_msg: schemas.ChatMessage,
    request: Request,
    session: models.StudentSession = Depends(get_current_session),
    prereq_service: PrerequisiteService = Depends(get_prerequisite_service),
    ai_service: AIService = Depends(get_ai_service),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
    __: None = Depends(ai_rate_limit),
):
    profile = session.profile
    if not profile:
        raise HTTPException(status_code=400, detail="Student profile not set")

    # Collect courses by status
    def codes_with_status(status: str) -> list[str]:
        return [c.course_code for c in session.courses if c.status == status and c.course_code]

    completed_courses = codes_with_status("completed")
    in_progress_courses = codes_with_status("in-progress")
    planned_courses_list = [c for c in session.courses if c.status == "planned"]
    planned_course_codes = codes_with_status("planned")

    # Calculate current planned credits
    current_planned_credits = sum(
        float(c.credits) if c.credits else 3.0  # Default to 3 if not set
        for c in planned_courses_list
    )

    eligible_codes = (
        prereq_service.get_eligible_courses(profile.program_code, _satisfied_course_codes(session))
        if profile.program_code
        else []
    )
    available_courses = []
    for code in eligible_codes:
        course_db = db.query(models.Course).filter(models.Course.code == code).first()
        entry = {"code": code, "title": course_db.title if course_db else code}
        if course_db is not None and course_db.credits:
            entry["credits"] = f"{float(course_db.credits):g}"
        available_courses.append(entry)

    # --- Compliance Guardrail (deterministic, runs before AI) ---
    is_compliant, compliance_warning = check_financial_aid_compliance(
        financial_aid_type=profile.financial_aid_type,
        planned_credits=current_planned_credits,
        enrollment_status=profile.enrollment_status,
        db=db,
    )
    if not is_compliant:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "compliance_violation",
                "aid_type": profile.financial_aid_type,
                "planned_credits": current_planned_credits,
                "message": compliance_warning,
            },
        )

    # --- Visa Guardrail (deterministic, runs before AI) ---
    visa_ok, visa_warning = check_visa_compliance(
        student_type=profile.student_type,
        planned_credits=current_planned_credits,
        planned_course_codes=planned_course_codes,
        db=db,
    )
    if not visa_ok:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "visa_compliance_violation",
                "student_type": profile.student_type,
                "planned_credits": current_planned_credits,
                "message": visa_warning,
            },
        )

    # Build compliance context for the AI — tell it what credit load is required
    warnings = []
    if profile.financial_aid_type in ("pell",):
        warnings.append(
            "Pell Grant: recommend at least 6 credits (half-time) to receive any award, 12 credits (full-time) for the full award."
        )
    if profile.financial_aid_type in ("tap", "both"):
        warnings.append(
            "TAP: must recommend exactly 12+ credits of degree-applicable courses (full-time required)."
        )
    if profile.financial_aid_type == "both":
        warnings.append("Pell Grant: 12 credits = 100% award; fewer credits = prorated award.")
    if profile.student_type == "international":
        warnings.append(
            "F-1 visa: must recommend at least 12 credits with no more than 1 online/hybrid course."
        )
    if not warnings:
        warnings.append(
            "No financial aid or visa constraints — recommend a standard full-time load (12–15 credits)."
        )

    async def generate(extra_warnings: list[str]) -> schemas.AdvisementResponse:
        try:
            return await ai_service.generate_advisement(
                profile=profile,
                completed_courses=completed_courses,
                in_progress_courses=in_progress_courses,
                planned_courses=planned_course_codes,
                available_courses=available_courses,
                warnings=warnings + extra_warnings,
                current_planned_credits=current_planned_credits,
                db=db,
                student_message=chat_msg.message,
            )
        except NoProviderConfiguredError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except AdvisementGenerationError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

    response = await generate([])

    # --- Plan guardrail (deterministic, runs after AI) ---
    # The AI is told the minimums but can still under-fill the plan. Give it one
    # corrective pass with the exact shortfall, then refuse a plan that still fails.
    violation = _plan_violations(profile, response, db)
    if violation:
        logger.warning(
            "Recommended plan failed compliance, retrying once: %s", violation["message"]
        )
        response = await generate(
            [
                f"REJECTED: your previous plan failed compliance. {violation['message']} "
                "Recommend a plan that meets every minimum."
            ]
        )
        violation = _plan_violations(profile, response, db)
    if violation:
        logger.warning("Recommended plan still failed compliance after retry")
        raise HTTPException(status_code=422, detail=violation)
    response.compliance_cleared = True

    # --- TAP elective check (post-AI annotation, not a hard block) ---
    check_tap_elective_compliance(
        financial_aid_type=profile.financial_aid_type,
        program_code=profile.program_code,
        recommended_courses=response.recommended_courses,
        db=db,
    )

    # Pell proration: use the credits the AI actually recommended, not pre-existing planned courses
    recommended_credits = sum(c.credits for c in response.recommended_courses)
    proration_data = calculate_pell_proration(
        financial_aid_type=profile.financial_aid_type,
        planned_credits=recommended_credits,
    )
    if proration_data:
        response.pell_proration = schemas.PellProration(**proration_data)

    # Update total_planned_credits in the response to reflect AI recommendations
    response.total_planned_credits = recommended_credits

    return response
