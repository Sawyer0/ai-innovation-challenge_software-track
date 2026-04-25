import json
import os
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from ..models import Course, Program, CoursePrerequisite, ProgramRequirement, EnrollmentStatusRule, FinancialAidConstraint
from ..database import SessionLocal, engine, Base
from decimal import Decimal

# --- Pydantic Validation Models for Scraped JSON ---

class ScrapedPrerequisite(BaseModel):
    text: Optional[str] = None

class ScrapedComponent(BaseModel):
    type: Optional[str] = None
    contact_hours: Optional[Any] = None
    workload_hours: Optional[Any] = None
    instruction_mode: Optional[str] = None

class ScrapedCourse(BaseModel):
    code: str = Field(..., max_length=20)
    title: str = Field(default="", max_length=255)
    long_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    credits: Any = Field(default=0)
    subject: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    hegis_code: Optional[str] = Field(None, max_length=20)
    typically_offered: Optional[str] = Field(None, max_length=100)
    components: Optional[List[ScrapedComponent]] = []
    prerequisites: Optional[List[ScrapedPrerequisite]] = []

class ScrapedElectiveGroup(BaseModel):
    name: str = Field(default="Elective", max_length=100)
    courses: List[str] = []

class ScrapedSemester(BaseModel):
    year: str = Field(default="Year 1", max_length=20)
    semester: str = Field(default="Semester 1", max_length=20)
    required_courses: List[str] = []
    elective_groups: List[ScrapedElectiveGroup] = []

class ScrapedProgram(BaseModel):
    programCode: str = Field(..., max_length=50)
    name: str = Field(default="", max_length=255)
    description: Optional[str] = None
    degree: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    hegisCode: Optional[str] = Field(None, max_length=20)
    semesters: Optional[List[ScrapedSemester]] = []

class ScrapedCatalog(BaseModel):
    courses: List[ScrapedCourse] = []
    programs: List[ScrapedProgram] = []

# ----------------------------------------------------

# Enrollment status rules per CUNY policy
_ENROLLMENT_STATUS_RULES = [
    dict(status_name="full-time",           min_credits=12, max_credits=18, description="Full-time (12–18 credits)"),
    dict(status_name="half-time",           min_credits=6,  max_credits=11, description="Half-time (6–11 credits)"),
    dict(status_name="less-than-half-time", min_credits=0,  max_credits=5,  description="Less than half-time (0–5 credits)"),
]

# Financial aid credit minimums per CUNY/federal rules
# block_underload=True → guardrail returns 422 before AI runs
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


def seed_policy_data(db: Session) -> None:
    """
    Idempotently inserts enrollment status rules and financial aid constraints.
    Safe to call on every startup — skips rows that already exist.
    """
    for rule_data in _ENROLLMENT_STATUS_RULES:
        exists = db.query(EnrollmentStatusRule).filter(
            EnrollmentStatusRule.status_name == rule_data["status_name"]
        ).first()
        if not exists:
            db.add(EnrollmentStatusRule(**rule_data))

    for constraint_data in _FINANCIAL_AID_CONSTRAINTS:
        exists = db.query(FinancialAidConstraint).filter(
            FinancialAidConstraint.aid_type == constraint_data["aid_type"]
        ).first()
        if not exists:
            db.add(FinancialAidConstraint(**constraint_data))

    db.commit()
    print("Policy data seeded (enrollment rules + financial aid constraints).")


def load_catalog(json_path: str):
    print(f"Loading catalog from {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    print("Validating raw JSON data with Pydantic...")
    try:
        data = ScrapedCatalog.model_validate(raw_data)
        print("Validation successful!")
    except ValidationError as ve:
        print(f"Validation Error: {ve}")
        return

    # Ensure tables exist
    print("Recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    try:
        # Load Courses
        print(f"Found {len(data.courses)} courses. Inserting...")
        course_map = {} # code -> Course object
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
            for comp in (c_data.components or []):
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
                instruction_mode=instruction_mode,
                raw_data=c_data.model_dump()
            )
            db.add(course)
            course_map[course.code] = course

        db.commit()
        
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
                cp = CoursePrerequisite(
                    course_id=course.id,
                    is_corequisite=False,
                    notes=text
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
                raw_data=p_data.model_dump()
            )
            db.add(program)
            db.commit() # commit to get program.id
            
            # Load Program Requirements (Degree Map)
            if p_data.semesters:
                for sem in p_data.semesters:
                    # Required Courses
                    for req_course_code in sem.required_courses:
                        pr = ProgramRequirement(
                            program_id=program.id,
                            course_code=req_course_code,
                            semester_year=sem.year,
                            semester_term=sem.semester,
                            is_required=True,
                            elective_group=None
                        )
                        db.add(pr)
                        
                    # Elective Groups
                    for elect_group in sem.elective_groups:
                        for elect_course_code in elect_group.courses:
                            pr = ProgramRequirement(
                                program_id=program.id,
                                course_code=elect_course_code,
                                semester_year=sem.year,
                                semester_term=sem.semester,
                                is_required=False,
                                elective_group=elect_group.name
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

if __name__ == "__main__":
    catalog_path = os.path.join(os.path.dirname(__file__), "../../../bmcc-catalog.json")
    load_catalog(catalog_path)
