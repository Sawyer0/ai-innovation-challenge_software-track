from pydantic import BaseModel, Field, constr
from typing import List, Optional, Any
from decimal import Decimal
from datetime import datetime

class CourseBase(BaseModel):
    code: str = Field(..., max_length=20)
    title: str = Field(..., max_length=255)
    long_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    credits: Decimal = Field(..., ge=0)
    subject: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    hegis_code: Optional[str] = Field(None, max_length=20)
    typically_offered: Optional[str] = Field(None, max_length=100)

class Course(CourseBase):
    id: int

    class Config:
        from_attributes = True

class CourseDetail(Course):
    raw_data: Optional[Any] = None

class ProgramBase(BaseModel):
    program_code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    long_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    degree: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    hegis_code: Optional[str] = Field(None, max_length=20)

class Program(ProgramBase):
    id: int

    class Config:
        from_attributes = True

class StudentProfileBase(BaseModel):
    school: Optional[str] = Field(None, max_length=100)
    program_code: Optional[str] = Field(None, max_length=50)
    enrollment_status: Optional[str] = Field(None, max_length=50)
    student_type: Optional[str] = Field(None, max_length=50)
    financial_aid_type: Optional[str] = Field(None, max_length=50)
    graduation_year: Optional[int] = Field(None, ge=1900, le=2100)
    graduation_semester: Optional[str] = Field(None, max_length=20)

class StudentCourseBase(BaseModel):
    course_code: str = Field(..., max_length=20)
    semester_taken: Optional[str] = Field(None, max_length=20)
    status: str = Field(..., max_length=20)
    grade: Optional[str] = Field(None, max_length=5)
    credits: Decimal = Field(..., ge=0)
    source: Optional[str] = Field(None, max_length=50)

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

class ChatResponse(BaseModel):
    response: str
