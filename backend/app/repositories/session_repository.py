from sqlalchemy.orm import Session
from ..models import StudentSession, StudentProfile, StudentCourse
from .base import BaseRepository

class SessionRepository(BaseRepository):
    def get_by_session_id(self, session_id: str) -> StudentSession:
        return self.db.query(StudentSession).filter(StudentSession.session_id == session_id).first()

    def create_session(self, session_id: str) -> StudentSession:
        db_session = StudentSession(session_id=session_id)
        self.db.add(db_session)
        self.db.commit()
        self.db.refresh(db_session)
        return db_session

    def get_profile(self, session_id: str) -> StudentProfile:
        return self.db.query(StudentProfile).filter(StudentProfile.session_id == session_id).first()

    def create_profile(self, session_id: str) -> StudentProfile:
        profile = StudentProfile(session_id=session_id)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile
    
    def update_profile(self, profile: StudentProfile, data: dict) -> StudentProfile:
        for key, value in data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_course(self, session_id: str, course_code: str) -> StudentCourse:
        return self.db.query(StudentCourse).filter(
            StudentCourse.session_id == session_id,
            StudentCourse.course_code == course_code
        ).first()

    def add_course(self, session_id: str, course_data: dict) -> StudentCourse:
        student_course = StudentCourse(
            session_id=session_id,
            course_code=course_data.get("course_code"),
            semester_taken=course_data.get("semester_taken"),
            status=course_data.get("status"),
            grade=course_data.get("grade"),
            credits=course_data.get("credits"),
            source=course_data.get("source", "manual")
        )
        self.db.add(student_course)
        self.db.commit()
        self.db.refresh(student_course)
        return student_course

    def delete_course(self, course: StudentCourse) -> None:
        self.db.delete(course)
        self.db.commit()
