from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from ..models import Course
from .base import BaseRepository


class CourseRepository(BaseRepository[Course]):
    """Repository for Course entity operations."""

    def __init__(self, db: Session):
        super().__init__(db, Course)

    def get_by_code(self, code: str) -> Optional[Course]:
        """Get course by its code."""
        return self.get_by_field("code", code)

    def list_paginated(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Course]:
        """List courses with optional search filtering."""
        query = self.db.query(Course)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Course.code.ilike(search_term),
                    Course.title.ilike(search_term),
                    Course.department.ilike(search_term)
                )
            )
        return query.offset(skip).limit(limit).all()
