from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from ..models import Course
from .base import BaseRepository

class CourseRepository(BaseRepository):
    def get_by_code(self, code: str) -> Optional[Course]:
        return self.db.query(Course).filter(Course.code == code).first()

    def list_paginated(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Course]:
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
