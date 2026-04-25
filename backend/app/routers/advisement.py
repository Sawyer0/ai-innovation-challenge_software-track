from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, models
from ..dependencies import get_current_session, get_prerequisite_service, get_ai_service, get_db
from ..dependencies.rate_limit import rate_limit
from ..services.prerequisite_service import PrerequisiteService
from ..services.ai_service import AIService
from ..utils import check_financial_aid_compliance, check_visa_compliance, calculate_pell_proration, check_tap_elective_compliance

router = APIRouter(prefix="/api/session", tags=["advisement"])

@router.get("/{session_id}/advisement/eligible")
def get_eligible_courses(
    session: models.StudentSession = Depends(get_current_session),
    prereq_service: PrerequisiteService = Depends(get_prerequisite_service)
):
    try:
        profile = session.profile
        if not profile or not profile.program_code:
            raise HTTPException(status_code=400, detail="Student profile or program code not set")
            
        completed_courses = [c.course_code for c in session.courses if c.status == "completed"]
        remaining_reqs = prereq_service.get_remaining_requirements(profile.program_code, completed_courses)
        
        eligible = []
        for req in remaining_reqs:
            if prereq_service.check_prerequisites(req, completed_courses):
                eligible.append(req)
                
        return {"eligible_courses": eligible}
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/{session_id}/advisement", response_model=schemas.AdvisementResponse)
async def advisement(
    chat_msg: schemas.ChatMessage,
    request: Request,
    session: models.StudentSession = Depends(get_current_session),
    prereq_service: PrerequisiteService = Depends(get_prerequisite_service),
    ai_service: AIService = Depends(get_ai_service),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit)
):
    profile = session.profile
    if not profile:
        raise HTTPException(status_code=400, detail="Student profile not set")

    # Collect courses by status
    completed_courses = [c.course_code for c in session.courses if c.status == "completed"]
    in_progress_courses = [c.course_code for c in session.courses if c.status == "in-progress"]
    planned_courses_list = [c for c in session.courses if c.status == "planned"]
    planned_course_codes = [c.course_code for c in planned_courses_list]

    # Calculate current planned credits
    current_planned_credits = sum(
        float(c.credits) if c.credits else 3.0  # Default to 3 if not set
        for c in planned_courses_list
    )

    # Treat in-progress courses as satisfying prerequisites (the student is enrolled)
    courses_for_prereqs = list(set(completed_courses + in_progress_courses))

    # Get remaining requirements and check eligibility
    remaining_reqs = prereq_service.get_remaining_requirements(profile.program_code, courses_for_prereqs) if profile.program_code else []

    # Get full course details from database for available courses
    seen_codes: set[str] = set()
    available_courses = []
    for req in remaining_reqs:
        if req in seen_codes:
            continue
        if prereq_service.check_prerequisites(req, courses_for_prereqs):
            seen_codes.add(req)
            course_db = db.query(models.Course).filter(models.Course.code == req).first()
            available_courses.append({
                "code": req,
                "title": course_db.title if course_db else req
            })

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
        warnings.append("Pell Grant: recommend at least 6 credits (half-time) to receive any award, 12 credits (full-time) for the full award.")
    if profile.financial_aid_type in ("tap", "both"):
        warnings.append("TAP: must recommend exactly 12+ credits of degree-applicable courses (full-time required).")
    if profile.financial_aid_type == "both":
        warnings.append("Pell Grant: 12 credits = 100% award; fewer credits = prorated award.")
    if profile.student_type == "international":
        warnings.append("F-1 visa: must recommend at least 12 credits with no more than 1 online/hybrid course.")
    if not warnings:
        warnings.append("No financial aid or visa constraints — recommend a standard full-time load (12–15 credits).")

    response = await ai_service.generate_advisement(
        profile=profile,
        completed_courses=completed_courses,
        in_progress_courses=in_progress_courses,
        planned_courses=planned_course_codes,
        available_courses=available_courses,
        warnings=warnings,
        current_planned_credits=current_planned_credits,
        db=db,
        student_message=chat_msg.message,
    )

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
