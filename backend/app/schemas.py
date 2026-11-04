from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class CourseBase(BaseModel):
    code: str = Field(..., max_length=20)
    title: str = Field(..., max_length=255)
    long_name: str | None = Field(None, max_length=255)
    description: str | None = None
    credits: Decimal = Field(..., ge=0)
    subject: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=100)
    hegis_code: str | None = Field(None, max_length=20)
    typically_offered: str | None = Field(None, max_length=100)


class Course(CourseBase):
    id: int

    class Config:
        from_attributes = True


class CourseDetail(Course):
    raw_data: Any | None = None


class ProgramBase(BaseModel):
    program_code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    long_name: str | None = Field(None, max_length=255)
    description: str | None = None
    degree: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=100)
    hegis_code: str | None = Field(None, max_length=20)


class Program(ProgramBase):
    id: int

    class Config:
        from_attributes = True


class StudentProfileBase(BaseModel):
    school: str | None = Field(None, max_length=100)
    program_code: str | None = Field(None, max_length=50)
    enrollment_status: str | None = Field(None, max_length=50)
    student_type: str | None = Field(None, max_length=50)
    classification: str | None = Field(None, max_length=50)
    academic_standing: str | None = Field(None, max_length=50)
    financial_aid_type: str | None = Field(None, max_length=50)
    graduation_year: int | None = Field(None, ge=1900, le=2100)
    graduation_semester: str | None = Field(None, max_length=20)
    career_goal: str | None = None


class StudentCourseBase(BaseModel):
    course_code: str = Field(..., max_length=20)
    semester_taken: str | None = Field(None, max_length=20)
    status: str = Field(..., max_length=20)
    grade: str | None = Field(None, max_length=5)
    credits: Decimal = Field(..., ge=0)
    source: str | None = Field(None, max_length=50)


class SessionCreate(BaseModel):
    # Empty request body to create a session
    pass


class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    last_activity: datetime

    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    message: str


class RecommendedCourse(BaseModel):
    course_code: str
    course_title: str
    credits: float
    requirement_satisfied: str  # which degree requirement this fulfills
    compliance_status: str  # "compliant", "warning", or "blocked"
    compliance_note: str | None  # populated only when not compliant
    career_rationale: str  # how this course connects to the student's career goal
    why_now: str  # why this course makes sense this semester specifically


class PellProration(BaseModel):
    planned_credits: float
    percentage: float  # 0.25 / 0.50 / 0.75 / 1.00
    percentage_display: str  # "75%"
    enrollment_tier: str  # "half-time", "three-quarter-time", etc.
    note: str  # plain-English explanation for the student


class AdvisementResponse(BaseModel):
    next_semester: str
    total_planned_credits: float
    compliance_cleared: bool
    advisor_message: str  # conversational opening/closing paragraph
    recommended_courses: list[RecommendedCourse]
    pell_proration: PellProration | None = None  # None when student has no Pell
    disclaimer: str = (
        "Always confirm your final schedule with your advisor and DegreeWorks before registering."
    )


class ChatResponse(BaseModel):
    response: str
