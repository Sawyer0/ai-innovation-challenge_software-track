from typing import Dict, Any, List
from ..models import StudentSession, StudentProfile, StudentCourse
from ..repositories.session_repository import SessionRepository
from .base import BaseService

class SessionService(BaseService):
    def __init__(self, repo: SessionRepository):
        self.repo = repo
        
    def create_session(self, session_id: str) -> StudentSession:
        return self.repo.create_session(session_id)

    def get_session_with_data(self, session_id: str) -> dict:
        session = self.repo.get_by_session_id(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "profile": session.profile,
            "courses": session.courses
        }

    def set_profile(self, session_id: str, data: Dict[str, Any]) -> StudentProfile:
        profile = self.repo.get_profile(session_id)
        if not profile:
            profile = self.repo.create_profile(session_id)
        
        return self.repo.update_profile(profile, data)

    def add_course(self, session_id: str, data: Dict[str, Any]) -> StudentCourse:
        return self.repo.add_course(session_id, data)
        
    def add_courses_bulk(self, session_id: str, courses_data: List[Dict[str, Any]]) -> List[StudentCourse]:
        saved_courses = []
        for course_data in courses_data:
            course = self.repo.add_course(session_id, course_data)
            saved_courses.append(course)
        return saved_courses

    def delete_course(self, session_id: str, course_code: str) -> bool:
        course = self.repo.get_course(session_id, course_code)
        if not course:
            return False
        self.repo.delete_course(course)
        return True
