"""
Cleanup service for session expiry and maintenance.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from ..repositories.cleanup_repository import CleanupRepository
from ..models import StudentSession


class CleanupService:
    """Service for cleanup operations."""
    
    # Default session expiry: 30 days
    DEFAULT_SESSION_DAYS = 30
    
    def __init__(self, db: Session):
        self.db = db
        self.cleanup_repo = CleanupRepository(db)
    
    def set_session_expiry(
        self, 
        session_id: str, 
        days: Optional[int] = None
    ) -> Optional[StudentSession]:
        """
        Set expiry date for a session.
        
        Args:
            session_id: Session to update
            days: Days until expiry (default: 30)
            
        Returns:
            Updated session or None if not found
        """
        session = (
            self.db.query(StudentSession)
            .filter(StudentSession.session_id == session_id)
            .first()
        )
        
        if not session:
            return None
        
        days = days or self.DEFAULT_SESSION_DAYS
        session.expires_at = datetime.utcnow() + timedelta(days=days)
        self.db.commit()
        
        return session
    
    def is_session_valid(self, session_id: str) -> bool:
        """
        Check if session exists and has not expired.
        
        Args:
            session_id: Session to check
            
        Returns:
            True if valid and not expired
        """
        session = (
            self.db.query(StudentSession)
            .filter(StudentSession.session_id == session_id)
            .first()
        )
        
        if not session:
            return False
        
        if session.expires_at and session.expires_at < datetime.utcnow():
            return False
        
        return True
    
    def cleanup_expired_sessions(self) -> dict:
        """
        Run cleanup of all expired sessions.
        
        Returns:
            Dict with cleanup statistics
        """
        now = datetime.utcnow()
        
        # Get count before deletion
        expired = self.cleanup_repo.get_expired_sessions(now)
        deleted_count = len(expired)
        
        # Delete them
        for session in expired:
            self.db.delete(session)
        
        # Clean up orphaned data
        orphaned_courses = self.cleanup_repo.delete_orphaned_courses()
        
        self.db.commit()
        
        return {
            "expired_sessions_deleted": deleted_count,
            "orphaned_courses_deleted": orphaned_courses,
            "timestamp": now.isoformat()
        }
    
    def get_session_status(self, session_id: str) -> Optional[dict]:
        """
        Get detailed status of a session.
        
        Returns:
            Dict with status info or None if not found
        """
        session = (
            self.db.query(StudentSession)
            .filter(StudentSession.session_id == session_id)
            .first()
        )
        
        if not session:
            return None
        
        now = datetime.utcnow()
        is_expired = bool(
            session.expires_at and session.expires_at < now
        )
        
        return {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "last_activity": session.last_activity.isoformat() if session.last_activity else None,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "is_expired": is_expired,
            "is_valid": not is_expired,
            "days_remaining": (
                (session.expires_at - now).days 
                if session.expires_at and not is_expired 
                else 0
            ) if session.expires_at else None
        }
