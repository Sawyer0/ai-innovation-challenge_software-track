from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, models
from ..dependencies import get_current_session, get_prerequisite_service, get_ai_service, get_db
from ..dependencies.rate_limit import rate_limit
from ..services.prerequisite_service import PrerequisiteService
from ..services.ai_service import AIService

router = APIRouter(prefix="/api/advisement", tags=["advisement"])

@router.get("/eligible")
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

@router.post("/")
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

    # Get remaining requirements and check eligibility
    remaining_reqs = prereq_service.get_remaining_requirements(profile.program_code, completed_courses) if profile.program_code else []

    # Get full course details from database for available courses
    available_courses = []
    for req in remaining_reqs:
        if prereq_service.check_prerequisites(req, completed_courses):
            # Query database for actual course title
            course_db = db.query(models.Course).filter(models.Course.code == req).first()
            available_courses.append({
                "code": req,
                "title": course_db.title if course_db else req
            })

    # Build warnings based on student profile
    warnings = []
    if profile.financial_aid_type:
        warnings.append(f"Financial aid ({profile.financial_aid_type}) requires maintaining enrollment requirements")

    response = await ai_service.generate_advisement(
        profile=profile,
        completed_courses=completed_courses,
        in_progress_courses=in_progress_courses,
        planned_courses=planned_course_codes,
        available_courses=available_courses,
        warnings=warnings,
        current_planned_credits=current_planned_credits,
        db=db,
        student_message=chat_msg.message
    )

    return schemas.ChatResponse(response=response)
