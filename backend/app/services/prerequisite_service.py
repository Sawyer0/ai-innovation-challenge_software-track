from ..academics.grades import meets_minimum_grade
from ..models import CoursePrerequisite
from ..repositories.course_repository import CourseRepository
from ..repositories.program_repository import ProgramRepository


class PrerequisiteService:
    def __init__(self, program_repo: ProgramRepository, course_repo: CourseRepository):
        self.program_repo = program_repo
        self.course_repo = course_repo

    def get_prerequisites(self, course_code: str) -> list[CoursePrerequisite]:
        course = self.course_repo.get_by_code(course_code)
        return course.prerequisites if course else []

    def check_prerequisites(self, course_code: str, completed_courses: list[str]) -> bool:
        """
        Check if prerequisites are met (basic check without grades).

        Args:
            course_code: Course to check prerequisites for
            completed_courses: List of completed course codes

        Returns:
            True if all prerequisite groups are satisfied
        """
        prereqs = self.get_prerequisites(course_code)
        if not prereqs:
            return True

        groups = {}
        for p in prereqs:
            if p.logic_group not in groups:
                groups[p.logic_group] = []
            groups[p.logic_group].append(p.prerequisite_course_code)

        for _logic_group, course_options in groups.items():
            if not any(c in completed_courses for c in course_options):
                return False

        return True

    def check_prerequisites_with_grades(
        self,
        course_code: str,
        completed_courses: list[tuple[str, str]],  # [(code, grade), ...]
    ) -> tuple[bool, list[str]]:
        """
        Check prerequisites with grade requirements.

        Args:
            course_code: Course to check prerequisites for
            completed_courses: List of (course_code, grade) tuples

        Returns:
            Tuple of (is_satisfied: bool, missing_prereqs: list)
        """
        prereqs = self.get_prerequisites(course_code)
        if not prereqs:
            return True, []

        # Convert to dict for easy lookup
        completed_with_grades: dict[str, str] = {}
        for code, grade in completed_courses:
            normalized = code.upper().replace(" ", "")
            # Keep highest grade if duplicate
            if normalized in completed_with_grades:
                if meets_minimum_grade(grade, completed_with_grades[normalized]):
                    completed_with_grades[normalized] = grade
            else:
                completed_with_grades[normalized] = grade

        # Group by logic_group
        groups: dict[int, list[CoursePrerequisite]] = {}
        for p in prereqs:
            if p.logic_group not in groups:
                groups[p.logic_group] = []
            groups[p.logic_group].append(p)

        missing = []

        for _logic_group, prereq_list in groups.items():
            group_satisfied = False
            group_requirements = []

            for p in prereq_list:
                prereq_code = (
                    p.prerequisite_course_code.upper().replace(" ", "")
                    if p.prerequisite_course_code
                    else ""
                )
                min_grade = p.minimum_grade or "C"

                group_requirements.append(f"{p.prerequisite_course_code} (min {min_grade})")

                if prereq_code in completed_with_grades:
                    student_grade = completed_with_grades[prereq_code]
                    if meets_minimum_grade(student_grade, min_grade):
                        group_satisfied = True
                        break

            if not group_satisfied:
                missing.extend(group_requirements)

        return len(missing) == 0, missing

    def get_remaining_requirements(
        self, program_code: str, completed_course_codes: list[str]
    ) -> list[str]:
        program = self.program_repo.get_by_code(program_code)
        if not program:
            return []

        remaining = []
        for req in program.requirements:
            if req.course_code and req.course_code not in completed_course_codes:
                remaining.append(req.course_code)

        return remaining

    def get_eligible_courses(self, program_code: str, satisfied_codes: list[str]) -> list[str]:
        """Remaining program requirements whose prerequisites are met, in catalog order."""
        eligible: list[str] = []
        for code in self.get_remaining_requirements(program_code, satisfied_codes):
            if code not in eligible and self.check_prerequisites(code, satisfied_codes):
                eligible.append(code)
        return eligible
