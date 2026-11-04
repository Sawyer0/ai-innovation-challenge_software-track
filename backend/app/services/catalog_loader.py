import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from ..database import Base, SessionLocal, engine
from ..models import (
    AcademicPolicy,
    Course,
    CoursePrerequisite,
    EnrollmentStatusRule,
    FinancialAidConstraint,
    Program,
    ProgramRequirement,
)
from ..parsers.prerequisite_parser import CourseCodeIndex, parse_prerequisite_text, parse_wildcard

# --- Pydantic Validation Models for Scraped JSON ---


class ScrapedPrerequisite(BaseModel):
    text: str | None = None


class ScrapedComponent(BaseModel):
    type: str | None = None
    contact_hours: Any | None = None
    workload_hours: Any | None = None
    instruction_mode: str | None = None


class ScrapedCourse(BaseModel):
    code: str = Field(..., max_length=20)
    title: str = Field(default="", max_length=255)
    long_name: str | None = Field(None, max_length=255)
    description: str | None = None
    credits: Any = Field(default=0)
    subject: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=100)
    hegis_code: str | None = Field(None, max_length=20)
    typically_offered: str | None = Field(None, max_length=100)
    components: list[ScrapedComponent] | None = []
    prerequisites: list[ScrapedPrerequisite] | None = []


class ScrapedElectiveGroup(BaseModel):
    name: str = Field(default="Elective", max_length=100)
    courses: list[str] = []


class ScrapedSemester(BaseModel):
    year: str = Field(default="Year 1", max_length=20)
    semester: str = Field(default="Semester 1", max_length=20)
    required_courses: list[str] = []
    elective_groups: list[ScrapedElectiveGroup] = []


class ScrapedProgram(BaseModel):
    programCode: str = Field(..., max_length=50)
    name: str = Field(default="", max_length=255)
    description: str | None = None
    degree: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=100)
    hegisCode: str | None = Field(None, max_length=20)
    semesters: list[ScrapedSemester] | None = []


class ScrapedCatalog(BaseModel):
    courses: list[ScrapedCourse] = []
    programs: list[ScrapedProgram] = []


# --- Pydantic Models for rules.json ---


class ScrapedEnrollmentRule(BaseModel):
    status_name: str = Field(..., max_length=50)
    min_credits: float
    max_credits: float | None = None
    description: str | None = None
    is_default: bool = False


class ScrapedAidConstraint(BaseModel):
    aid_type: str = Field(..., max_length=50)
    min_credits_required: float | None = None
    min_status_required: str | None = Field(None, max_length=50)
    warning_message: str | None = None
    block_underload: bool = False
    allow_exception_process: bool = False


class ScrapedAcademicPolicy(BaseModel):
    policy_type: str = Field(..., max_length=50)
    policy_code: str | None = Field(None, max_length=50)
    description: str
    rule_logic: dict | None = None
    applies_to_student_types: list[str] | None = None
    applies_to_classifications: list[str] | None = None
    applies_to_academic_standings: list[str] | None = None
    applies_to_programs: list[str] | None = None
    priority: int = 100
    is_active: bool = True


class ScrapedRules(BaseModel):
    enrollment_status_rules: list[ScrapedEnrollmentRule] = []
    financial_aid_constraints: list[ScrapedAidConstraint] = []
    academic_policies: list[ScrapedAcademicPolicy] = []


# ----------------------------------------------------

# Enrollment status rules per CUNY policy (used by seed_policy_data as fallback)
_ENROLLMENT_STATUS_RULES = [
    dict(
        status_name="full-time",
        min_credits=12,
        max_credits=18,
        description="Full-time (12–18 credits)",
    ),
    dict(
        status_name="half-time",
        min_credits=6,
        max_credits=11,
        description="Half-time (6–11 credits)",
    ),
    dict(
        status_name="less-than-half-time",
        min_credits=0,
        max_credits=5,
        description="Less than half-time (0–5 credits)",
    ),
]

# Financial aid credit minimums per CUNY/federal rules
_FINANCIAL_AID_CONSTRAINTS = [
    dict(
        aid_type="pell",
        min_credits_required=6,
        min_status_required="half-time",
        warning_message=(
            "Your Pell Grant requires at least 6 credits (half-time enrollment). "
            "Dropping below 6 credits will reduce or eliminate your award. "
            "Please add more courses or speak with a financial aid advisor before registering."
        ),
        block_underload=True,
        allow_exception_process=True,
    ),
    dict(
        aid_type="tap",
        min_credits_required=12,
        min_status_required="full-time",
        warning_message=(
            "TAP (Tuition Assistance Program) requires full-time enrollment of at least 12 credits. "
            "Dropping below 12 credits will result in loss of TAP funding for this semester. "
            "Please add more courses or speak with a financial aid advisor before registering."
        ),
        block_underload=True,
        allow_exception_process=True,
    ),
    dict(
        aid_type="both",
        min_credits_required=12,
        min_status_required="full-time",
        warning_message=(
            "You receive both Pell Grant and TAP. TAP requires full-time enrollment (12+ credits). "
            "Dropping below 12 credits will affect both awards. "
            "Please speak with a financial aid advisor before making any schedule changes."
        ),
        block_underload=True,
        allow_exception_process=True,
    ),
]


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def initialize_database() -> None:
    """Create tables, load the bundled catalog on first run, and seed policy data."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        catalog_path = DATA_DIR / "bmcc-catalog.json"
        if db.query(Course).count() == 0 and catalog_path.exists():
            load_catalog(str(catalog_path))
            rules_path = DATA_DIR / "rules.json"
            if rules_path.exists():
                load_rules(str(rules_path))
        seed_policy_data(db)
    finally:
        db.close()


def seed_policy_data(db: Session) -> None:
    """Idempotently inserts enrollment status rules and financial aid constraints."""
    for rule_data in _ENROLLMENT_STATUS_RULES:
        exists = (
            db.query(EnrollmentStatusRule)
            .filter(EnrollmentStatusRule.status_name == rule_data["status_name"])
            .first()
        )
        if not exists:
            db.add(EnrollmentStatusRule(**rule_data))

    for constraint_data in _FINANCIAL_AID_CONSTRAINTS:
        exists = (
            db.query(FinancialAidConstraint)
            .filter(FinancialAidConstraint.aid_type == constraint_data["aid_type"])
            .first()
        )
        if not exists:
            db.add(FinancialAidConstraint(**constraint_data))

    db.commit()
    print("Policy data seeded (enrollment rules + financial aid constraints).")


def load_catalog(json_path: str):
    print(f"Loading catalog from {json_path}...")
    with open(json_path, encoding="utf-8") as f:
        raw_data = json.load(f)

    print("Validating raw JSON data with Pydantic...")
    try:
        data = ScrapedCatalog.model_validate(raw_data)
        print("Validation successful!")
    except ValidationError as ve:
        print(f"Validation Error: {ve}")
        return

    # Only drop and recreate catalog tables — preserve session/profile/course data
    print("Recreating catalog tables...")
    _CATALOG_TABLES = ["course_prerequisites", "program_requirements", "programs", "courses"]
    for tname in _CATALOG_TABLES:
        if tname in Base.metadata.tables:
            Base.metadata.tables[tname].drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    try:
        # Load Courses
        print(f"Found {len(data.courses)} courses. Inserting...")
        course_map = {}
        seen_codes = set()

        for c_data in data.courses:
            if c_data.code in seen_codes:
                continue
            seen_codes.add(c_data.code)

            try:
                credit_val = Decimal(str(c_data.credits))
            except Exception:
                credit_val = Decimal(0)

            # Derive instruction_mode from the first component that has one
            instruction_mode = None
            for comp in c_data.components or []:
                if comp.instruction_mode and comp.instruction_mode.strip():
                    instruction_mode = comp.instruction_mode.strip()
                    break

            course = Course(
                code=c_data.code,
                title=c_data.title,
                long_name=c_data.long_name,
                description=c_data.description,
                credits=credit_val,
                subject=c_data.subject,
                department=c_data.department,
                hegis_code=c_data.hegis_code,
                typically_offered=c_data.typically_offered,
            )
            db.add(course)
            course_map[course.code] = course

        db.commit()

        # Build fuzzy lookup index for course codes
        code_index = CourseCodeIndex(course_map)

        # Load Prerequisites
        print("Loading prerequisites...")
        prereq_count = 0
        for c_data in data.courses:
            course = course_map.get(c_data.code)
            if not course or not c_data.prerequisites:
                continue

            for prereq in c_data.prerequisites:
                text = prereq.text.strip() if prereq.text else ""
                if not text:
                    continue

                parsed_entries = parse_prerequisite_text(text)
                for entry in parsed_entries:
                    cp = CoursePrerequisite(
                        course_id=course.id,
                        prerequisite_course_code=entry.course_code,
                        is_corequisite=entry.is_corequisite,
                        logic_group=entry.logic_group,
                        notes=entry.notes,
                        is_attribute=entry.is_attribute,
                        attribute_name=entry.attribute_name,
                        attribute_value=entry.attribute_value,
                    )
                    db.add(cp)
                    prereq_count += 1

        db.commit()
        print(f"Inserted {prereq_count} prerequisites.")

        # Load Programs
        print(f"Found {len(data.programs)} programs. Inserting...")
        seen_programs = set()
        for p_data in data.programs:
            if p_data.programCode in seen_programs:
                continue
            seen_programs.add(p_data.programCode)

            program = Program(
                program_code=p_data.programCode,
                name=p_data.name,
                long_name=p_data.name,
                description=p_data.description,
                degree=p_data.degree,
                department=p_data.department,
                hegis_code=p_data.hegisCode,
            )
            db.add(program)
            db.commit()  # commit to get program.id

            # Load Program Requirements (Degree Map)
            if p_data.semesters:
                for sem in p_data.semesters:
                    for req_course_code in sem.required_courses:
                        matched = code_index.lookup(req_course_code)
                        wildcard = parse_wildcard(req_course_code)

                        pr = ProgramRequirement(
                            program_id=program.id,
                            course_code=req_course_code,
                            semester_year=sem.year,
                            semester_term=sem.semester,
                            is_required=True,
                            elective_group=None,
                            min_credits=matched.credits
                            if matched
                            else (Decimal("3.0") if wildcard else None),
                            is_wildcard=bool(wildcard),
                            wildcard_subject=wildcard["subject"] if wildcard else None,
                            wildcard_level=wildcard["level"] if wildcard else None,
                        )
                        db.add(pr)

                    for elect_group in sem.elective_groups:
                        for elect_course_code in elect_group.courses:
                            matched = code_index.lookup(elect_course_code)
                            wildcard = parse_wildcard(elect_course_code)

                            pr = ProgramRequirement(
                                program_id=program.id,
                                course_code=elect_course_code,
                                semester_year=sem.year,
                                semester_term=sem.semester,
                                is_required=False,
                                elective_group=elect_group.name,
                                min_credits=matched.credits
                                if matched
                                else (Decimal("3.0") if wildcard else None),
                                is_wildcard=bool(wildcard),
                                wildcard_subject=wildcard["subject"] if wildcard else None,
                                wildcard_level=wildcard["level"] if wildcard else None,
                            )
                            db.add(pr)

        db.commit()
        print("Programs and Degree Maps inserted successfully.")

        print("Seeding policy data...")
        seed_policy_data(db)

    except Exception as e:
        db.rollback()
        print(f"Error loading catalog: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


def load_rules(json_path: str):
    print(f"Loading rules from {json_path}...")
    if not os.path.exists(json_path):
        print(f"Warning: Rules file not found at {json_path}")
        return

    with open(json_path, encoding="utf-8") as f:
        raw_data = json.load(f)

    try:
        data = ScrapedRules.model_validate(raw_data)
        print("Rules validation successful!")
    except ValidationError as ve:
        print(f"Rules Validation Error: {ve}")
        return

    db: Session = SessionLocal()
    try:
        # Clear existing rules to avoid duplicates on re-import
        db.query(EnrollmentStatusRule).delete()
        db.query(FinancialAidConstraint).delete()
        db.query(AcademicPolicy).delete()

        # Load Enrollment Rules
        for r in data.enrollment_status_rules:
            db.add(
                EnrollmentStatusRule(
                    status_name=r.status_name,
                    min_credits=Decimal(str(r.min_credits)),
                    max_credits=Decimal(str(r.max_credits)) if r.max_credits else None,
                    description=r.description,
                    is_default=r.is_default,
                )
            )

        # Load Aid Constraints
        for a in data.financial_aid_constraints:
            db.add(
                FinancialAidConstraint(
                    aid_type=a.aid_type,
                    min_credits_required=Decimal(str(a.min_credits_required))
                    if a.min_credits_required
                    else None,
                    min_status_required=a.min_status_required,
                    warning_message=a.warning_message,
                    block_underload=a.block_underload,
                    allow_exception_process=a.allow_exception_process,
                )
            )

        # Load Academic Policies
        for p in data.academic_policies:
            db.add(
                AcademicPolicy(
                    policy_type=p.policy_type,
                    policy_code=p.policy_code,
                    description=p.description,
                    rule_logic=p.rule_logic,
                    applies_to_student_types=p.applies_to_student_types,
                    applies_to_classifications=p.applies_to_classifications,
                    applies_to_academic_standings=p.applies_to_academic_standings,
                    applies_to_programs=p.applies_to_programs,
                    priority=p.priority,
                    is_active=p.is_active,
                )
            )

        db.commit()
        print("Rules imported successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error loading rules: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    catalog_path = os.path.join(os.path.dirname(__file__), "../../../bmcc-catalog.json")
    load_catalog(catalog_path)
