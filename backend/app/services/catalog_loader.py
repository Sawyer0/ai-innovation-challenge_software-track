import json
import os
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from ..models import Course, Program, CoursePrerequisite, ProgramRequirement, EnrollmentStatusRule, FinancialAidConstraint, AcademicPolicy
from ..database import SessionLocal, engine, Base
from ..parsers.prerequisite_parser import parse_prerequisite_text, CourseCodeIndex, parse_wildcard
from decimal import Decimal

# --- Pydantic Validation Models for Scraped JSON ---

class ScrapedPrerequisite(BaseModel):
    text: Optional[str] = None

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

# --- Pydantic Models for rules.json ---

class ScrapedEnrollmentRule(BaseModel):
    status_name: str = Field(..., max_length=50)
    min_credits: float
    max_credits: Optional[float] = None
    description: Optional[str] = None
    is_default: bool = False

class ScrapedAidConstraint(BaseModel):
    aid_type: str = Field(..., max_length=50)
    min_credits_required: Optional[float] = None
    min_status_required: Optional[str] = Field(None, max_length=50)
    warning_message: Optional[str] = None
    block_underload: bool = False
    allow_exception_process: bool = False

class ScrapedAcademicPolicy(BaseModel):
    policy_type: str = Field(..., max_length=50)
    policy_code: Optional[str] = Field(None, max_length=50)
    description: str
    rule_logic: Optional[dict] = None
    applies_to_student_types: Optional[List[str]] = None
    applies_to_programs: Optional[List[str]] = None
    priority: int = 100
    is_active: bool = True

class ScrapedRules(BaseModel):
    enrollment_status_rules: List[ScrapedEnrollmentRule] = []
    financial_aid_constraints: List[ScrapedAidConstraint] = []
    academic_policies: List[ScrapedAcademicPolicy] = []

# ----------------------------------------------------

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
                        attribute_value=entry.attribute_value
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
            db.commit() # commit to get program.id
            
            # Load Program Requirements (Degree Map)
            if p_data.semesters:
                for sem in p_data.semesters:
                    # Required Courses
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
                            min_credits=matched.credits if matched else (Decimal("3.0") if wildcard else None),
                            is_wildcard=bool(wildcard),
                            wildcard_subject=wildcard["subject"] if wildcard else None,
                            wildcard_level=wildcard["level"] if wildcard else None
                        )
                        db.add(pr)
                        
                    # Elective Groups
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
                                min_credits=matched.credits if matched else (Decimal("3.0") if wildcard else None),
                                is_wildcard=bool(wildcard),
                                wildcard_subject=wildcard["subject"] if wildcard else None,
                                wildcard_level=wildcard["level"] if wildcard else None
                            )
                            db.add(pr)
                        
        db.commit()
        print("Programs and Degree Maps inserted successfully.")

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

    with open(json_path, 'r', encoding='utf-8') as f:
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
            db.add(EnrollmentStatusRule(
                status_name=r.status_name,
                min_credits=Decimal(str(r.min_credits)),
                max_credits=Decimal(str(r.max_credits)) if r.max_credits else None,
                description=r.description,
                is_default=r.is_default
            ))

        # Load Aid Constraints
        for a in data.financial_aid_constraints:
            db.add(FinancialAidConstraint(
                aid_type=a.aid_type,
                min_credits_required=Decimal(str(a.min_credits_required)) if a.min_credits_required else None,
                min_status_required=a.min_status_required,
                warning_message=a.warning_message,
                block_underload=a.block_underload,
                allow_exception_process=a.allow_exception_process
            ))

        # Load Academic Policies
        for p in data.academic_policies:
            db.add(AcademicPolicy(
                policy_type=p.policy_type,
                policy_code=p.policy_code,
                description=p.description,
                rule_logic=p.rule_logic,
                applies_to_student_types=p.applies_to_student_types,
                applies_to_programs=p.applies_to_programs,
                priority=p.priority,
                is_active=p.is_active
            ))

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
