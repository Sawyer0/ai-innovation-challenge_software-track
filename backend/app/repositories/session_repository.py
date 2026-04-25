from sqlalchemy.orm import Session
from ..models import StudentSession, StudentProfile, StudentCourse
from .base import BaseRepository


class SessionRepository(BaseRepository[StudentSession]):
    """Repository for StudentSession and related entity operations."""

    def __init__(self, db: Session):
        super().__init__(db, StudentSession)

    def get_by_session_id(self, session_id: str) -> StudentSession:
        """Get session by its string identifier."""
        return self.db.query(StudentSession).filter(StudentSession.session_id == session_id).first()

    def create_session(self, session_id: str) -> StudentSession:
        """Create a new student session."""
        return self.create({"session_id": session_id})

    def get_profile(self, session_id: str) -> StudentProfile:
        """Get student profile by session ID."""
        return self.db.query(StudentProfile).filter(StudentProfile.session_id == session_id).first()

    def create_profile(self, session_id: str) -> StudentProfile:
        """Create a new student profile for a session."""
        profile = StudentProfile(session_id=session_id)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update_profile(self, profile: StudentProfile, data: dict) -> StudentProfile:
        """Update student profile with data dictionary."""
        for key, value in data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_course(self, session_id: str, course_code: str) -> StudentCourse:
        """Get a specific student course by session and course code."""
        return self.db.query(StudentCourse).filter(
            StudentCourse.session_id == session_id,
            StudentCourse.course_code == course_code
        ).first()

    def add_course(self, session_id: str, course_data: dict) -> StudentCourse:
        """Add a course to a student session."""
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
        """Delete a student course."""
        self.db.delete(course)
        self.db.commit()
