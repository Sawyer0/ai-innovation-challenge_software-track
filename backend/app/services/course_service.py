from ..models import Course
from ..repositories.course_repository import CourseRepository


class CourseService:
    def __init__(self, repo: CourseRepository):
        self.repo = repo

    def get_course(self, code: str) -> Course | None:
        return self.repo.get_by_code(code)

    def list_courses(
        self, skip: int = 0, limit: int = 100, search: str | None = None
    ) -> list[Course]:
        return self.repo.list_paginated(skip, limit, search)
