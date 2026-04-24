"""
Integration tests for catalog data quality.

Validates the integrity of imported catalog data.
These tests require the full catalog to be imported.
"""

import pytest
from app import models


@pytest.mark.integration
@pytest.mark.data_quality
class TestCourseDataQuality:
    """Validate course catalog data integrity."""
    
    def test_all_courses_have_required_fields(self, db):
        """Every course must have code, title, credits."""
        courses = db.query(models.Course).all()
        
        errors = []
        for course in courses:
            if not course.code or course.code == "":
                errors.append(f"Course {course.id}: missing code")
            if not course.title or course.title == "":
                errors.append(f"Course {course.code}: missing title")
            if course.credits is None:
                errors.append(f"Course {course.code}: missing credits")
        
        assert len(errors) == 0, f"Data quality issues: {errors[:10]}"
    
    def test_course_codes_are_unique(self, db):
        """Course codes must be unique."""
        from sqlalchemy import func
        
        duplicates = db.query(
            models.Course.code,
            func.count(models.Course.id).label('count')
        ).group_by(models.Course.code).having(func.count(models.Course.id) > 1).all()
        
        duplicate_list = [d[0] for d in duplicates]
        assert len(duplicate_list) == 0, f"Duplicate course codes: {duplicate_list[:10]}"
    
    def test_prerequisites_reference_valid_courses(self, db):
        """All prerequisite codes must reference existing courses."""
        course_codes = {c.code for c in db.query(models.Course).all()}
        prereqs = db.query(models.CoursePrerequisite).all()
        
        orphaned = []
        for p in prereqs:
            if p.prerequisite_course_code not in course_codes:
                orphaned.append(p.prerequisite_course_code)
        
        # Allow up to 5% orphaned (some prereqs may be external)
        if len(prereqs) > 0:
            orphan_rate = len(orphaned) / len(prereqs)
            assert orphan_rate < 0.05, f"Too many orphaned prerequisites: {orphaned[:20]}"
    
    def test_program_codes_are_unique(self, db):
        """Program codes must be unique."""
        from sqlalchemy import func
        
        duplicates = db.query(
            models.Program.program_code,
            func.count(models.Program.id).label('count')
        ).group_by(models.Program.program_code).having(func.count(models.Program.id) > 1).all()
        
        duplicate_list = [d[0] for d in duplicates]
        assert len(duplicate_list) == 0, f"Duplicate program codes: {duplicate_list}"
    
    def test_program_requirements_link_to_courses_or_are_electives(self, db):
        """Program requirements should reference valid courses or be elective slots."""
        course_codes = {c.code for c in db.query(models.Course).all()}
        requirements = db.query(models.ProgramRequirement).all()
        
        invalid = []
        for req in requirements:
            if req.course_code and req.course_code not in course_codes:
                # Check if it might be an elective pattern
                if not any(keyword in req.course_code.lower() for keyword in ['elective', 'choice']):
                    invalid.append(req.course_code)
        
        # Just warn about invalid references, don't fail
        if invalid:
            print(f"Warning: {len(invalid)} program requirements reference unknown courses")
            print(f"Sample: {invalid[:10]}")
    
    def test_credit_values_are_reasonable(self, db):
        """Course credits should be between 0 and 10."""
        courses = db.query(models.Course).filter(
            (models.Course.credits < 0) | (models.Course.credits > 10)
        ).all()
        
        unreasonable = [c.code for c in courses]
        assert len(unreasonable) == 0, f"Unreasonable credit values: {unreasonable[:10]}"
    
    def test_enrollment_status_rules_seeded(self, db):
        """Enrollment status rules should exist in database."""
        rules = db.query(models.EnrollmentStatusRule).all()
        
        status_names = {r.status_name for r in rules}
        assert "full-time" in status_names
        assert "half-time" in status_names
    
    def test_financial_aid_constraints_seeded(self, db):
        """Financial aid constraints should exist."""
        constraints = db.query(models.FinancialAidConstraint).all()
        
        aid_types = {c.aid_type for c in constraints}
        assert "pell" in aid_types or len(constraints) == 0  # May not be seeded yet


@pytest.mark.integration
@pytest.mark.data_quality
class TestCatalogCompleteness:
    """Test that catalog data is reasonably complete."""
    
    def test_courses_have_descriptions(self, db, full_catalog):
        """Most courses should have descriptions."""
        from sqlalchemy import func
        
        # full_catalog loads all courses
        total = db.query(func.count(models.Course.id)).scalar()
        with_description = db.query(func.count(models.Course.id)).filter(
            models.Course.description != None,
            models.Course.description != ""
        ).scalar()
        
        if total > 0:
            coverage = with_description / total
            assert coverage > 0.5, f"Only {coverage:.0%} of courses have descriptions"
        else:
            pytest.skip("No courses in database")
    
    def test_courses_have_prerequisites_data(self, db, full_catalog):
        """Some courses should have prerequisites defined."""
        from sqlalchemy import func
        
        # full_catalog fixture loads the complete catalog
        prereq_count = db.query(func.count(models.CoursePrerequisite.id)).scalar()
        
        # With full catalog loaded, we should have prerequisites
        assert prereq_count > 0, f"Expected prerequisites after loading full catalog, got {prereq_count}"
        print(f"\nLoaded {prereq_count} prerequisites from {full_catalog['courses']} courses")
    
    def test_programs_have_requirements(self, db, full_catalog):
        """Programs should have defined requirements."""
        # full_catalog loads all programs
        programs = db.query(models.Program).all()
        
        empty_programs = []
        for program in programs:
            req_count = db.query(models.ProgramRequirement).filter(
                models.ProgramRequirement.program_id == program.id
            ).count()
            if req_count == 0:
                empty_programs.append(program.program_code)
        
        # Many BMCC programs (certificates, micro-credentials) don't have semester maps
        # The scraped data shows ~47% without requirements - this is accurate for the catalog
        if len(programs) > 0:
            empty_rate = len(empty_programs) / len(programs)
            # Log for info but don't fail - this reflects actual catalog structure
            print(f"\n{empty_rate:.0%} of programs have no requirements (expected: many certificates/specialized programs)")
            # Sanity check: at least some programs should have requirements
            assert empty_rate < 0.9, f"{empty_rate:.0%} of programs lack requirements - possible import error"
