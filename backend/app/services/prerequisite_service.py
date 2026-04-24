from typing import List
from ..models import CoursePrerequisite, Program, ProgramRequirement, Course
from ..repositories.program_repository import ProgramRepository
from ..repositories.course_repository import CourseRepository

class PrerequisiteService:
    def __init__(self, program_repo: ProgramRepository, course_repo: CourseRepository):
        self.program_repo = program_repo
        self.course_repo = course_repo

    def get_prerequisites(self, course_code: str) -> List[CoursePrerequisite]:
        course = self.course_repo.get_by_code(course_code)
        return course.prerequisites if course else []

    def check_prerequisites(self, course_code: str, completed_course_codes: List[str]) -> bool:
        prereqs = self.get_prerequisites(course_code)
        if not prereqs:
            return True
            
        groups = {}
        for p in prereqs:
            if p.logic_group not in groups:
                groups[p.logic_group] = []
            groups[p.logic_group].append(p.prerequisite_course_code)
            
        for logic_group, course_options in groups.items():
            if not any(c in completed_course_codes for c in course_options):
                return False
                
        return True

    def get_remaining_requirements(self, program_code: str, completed_course_codes: List[str]) -> List[str]:
        program = self.program_repo.get_by_code(program_code)
        if not program:
            return []
            
        remaining = []
        for req in program.requirements:
            if req.course_code and req.course_code not in completed_course_codes:
                remaining.append(req.course_code)
                
        return remaining
