"""
Repository for cleanup operations - expired sessions and orphaned data.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models import StudentSession, StudentCourse, StudentProfile, PolicyException
from .base import BaseRepository


class CleanupRepository(BaseRepository):
    """Repository for cleanup and maintenance operations."""
    
    def get_expired_sessions(self, cutoff_date: datetime) -> List[StudentSession]:
        """
        Get all sessions that have expired.
        
        Args:
            cutoff_date: Sessions older than this are considered expired
            
        Returns:
            List of expired StudentSession objects
        """
        return (
            self.db.query(StudentSession)
            .filter(StudentSession.expires_at < cutoff_date)
            .all()
        )
    
    def get_inactive_sessions(
        self, 
        cutoff_date: datetime,
        include_expired: bool = False
    ) -> List[StudentSession]:
        """
        Get sessions inactive since cutoff date.
        
        Args:
            cutoff_date: Inactivity threshold
            include_expired: Whether to include already-expired sessions
            
        Returns:
            List of inactive StudentSession objects
        """
        query = self.db.query(StudentSession).filter(
            StudentSession.last_activity < cutoff_date
        )
        
        if not include_expired:
            query = query.filter(
                (StudentSession.expires_at.is_(None)) | 
                (StudentSession.expires_at > datetime.utcnow())
            )
        
        return query.all()
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all related data.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        session = (
            self.db.query(StudentSession)
            .filter(StudentSession.session_id == session_id)
            .first()
        )
        
        if not session:
            return False
        
        self.db.delete(session)
        return True
    
    def delete_expired_sessions(self, cutoff_date: datetime) -> int:
        """
        Bulk delete all expired sessions.
        
        Args:
            cutoff_date: Expiration threshold
            
        Returns:
            Number of sessions deleted
        """
        expired = self.get_expired_sessions(cutoff_date)
        count = len(expired)
        
        for session in expired:
            self.db.delete(session)
        
        return count
    
    def count_orphaned_courses(self) -> int:
        """Count courses with no valid session."""
        from sqlalchemy import exists
        
        return (
            self.db.query(StudentCourse)
            .filter(
                ~exists().where(
                    StudentSession.session_id == StudentCourse.session_id
                )
            )
            .count()
        )
    
    def delete_orphaned_courses(self) -> int:
        """Delete courses with no valid session."""
        from sqlalchemy import exists
        
        orphaned = (
            self.db.query(StudentCourse)
            .filter(
                ~exists().where(
                    StudentSession.session_id == StudentCourse.session_id
                )
            )
            .all()
        )
        
        count = len(orphaned)
        for course in orphaned:
            self.db.delete(course)
        
        return count
