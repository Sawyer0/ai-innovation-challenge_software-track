from typing import List, Optional
from ..models import Course
from ..repositories.course_repository import CourseRepository

class CourseService:
    def __init__(self, repo: CourseRepository):
        self.repo = repo

    def get_course(self, code: str) -> Optional[Course]:
        return self.repo.get_by_code(code)

    def list_courses(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Course]:
        return self.repo.list_paginated(skip, limit, search)
