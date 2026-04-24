import json
import os
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from ..models import Course, Program, CoursePrerequisite, ProgramRequirement
from ..database import SessionLocal, engine, Base
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
