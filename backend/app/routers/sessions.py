from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from .. import schemas, models
from ..dependencies import get_current_session, get_session_service, get_cleanup_service
from ..services.session_service import SessionService
from ..services.cleanup_service import CleanupService
from ..exceptions import SessionNotFoundError

router = APIRouter(prefix="/api/session", tags=["session"])

@router.post("/", response_model=schemas.SessionResponse)
def create_session(service: SessionService = Depends(get_session_service)):
    import uuid
    session_id = str(uuid.uuid4())
    return service.create_session(session_id)

@router.get("/{session_id}")
def get_session(
    session: models.StudentSession = Depends(get_current_session),
    service: SessionService = Depends(get_session_service)
):
    return service.get_session_with_data(session.session_id)

@router.post("/{session_id}/profile")
def set_profile(
    profile_data: schemas.StudentProfileBase,
    session: models.StudentSession = Depends(get_current_session),
    service: SessionService = Depends(get_session_service)
):
    return service.set_profile(session.session_id, profile_data.model_dump(exclude_unset=True))

@router.post("/{session_id}/courses")
def add_course(
    course_data: schemas.StudentCourseBase,
    session: models.StudentSession = Depends(get_current_session),
    service: SessionService = Depends(get_session_service)
):
    return service.add_course(session.session_id, course_data.model_dump())

@router.delete("/{session_id}/courses/{course_code}")
def delete_course(
    course_code: str,
    session: models.StudentSession = Depends(get_current_session),
    service: SessionService = Depends(get_session_service)
):
    success = service.delete_course(session.session_id, course_code)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"message": "Course deleted"}


@router.get("/{session_id}/status")
def get_session_status(
    session_id: str,
    cleanup_service: CleanupService = Depends(get_cleanup_service)
):
    """
    Check session validity and expiry status.
    
    Returns 410 Gone if session has expired.
    """
    status_info = cleanup_service.get_session_status(session_id)
    
    if not status_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if status_info["is_expired"]:
        raise HTTPException(
            status_code=410,
            detail={
                "message": "Session has expired",
                "expired_at": status_info["expires_at"]
            }
        )
    
    return status_info
