from sqlalchemy import Column, Integer, String, Boolean, Text, Numeric, JSON, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from .database import Base

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    long_name = Column(String(255))
    description = Column(Text)
    credits = Column(Numeric(4, 2))
    subject = Column(String(50))
    department = Column(String(100))
    hegis_code = Column(String(20))
    typically_offered = Column(String(100))
    raw_data = Column(JSON)

    prerequisites = relationship("CoursePrerequisite", back_populates="course")


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    prerequisite_course_code = Column(String(20))
    is_corequisite = Column(Boolean, default=False)
    logic_group = Column(Integer, default=1)
    notes = Column(Text)
    
    # New indexing columns for non-course attributes
    is_attribute = Column(Boolean, default=False)
    attribute_name = Column(String(50))
    attribute_value = Column(String(50))

    course = relationship("Course", back_populates="prerequisites")


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    program_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    long_name = Column(String(255))
    description = Column(Text)
    degree = Column(String(50))
    department = Column(String(100))
    hegis_code = Column(String(20))
    raw_data = Column(JSON)

    requirements = relationship("ProgramRequirement", back_populates="program")


class ProgramRequirement(Base):
    __tablename__ = "program_requirements"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("programs.id"))
    course_code = Column(String(20))
    semester_year = Column(String(20))
    semester_term = Column(String(20))
    is_required = Column(Boolean, default=True)
    elective_group = Column(String(50))
    min_credits = Column(Numeric(4, 2))
    
    # New indexing columns for wildcard patterns (e.g., "ART *")
    is_wildcard = Column(Boolean, default=False)
    wildcard_subject = Column(String(20))
    wildcard_level = Column(String(10))

    program = relationship("Program", back_populates="requirements")


class StudentSession(Base):
    __tablename__ = "student_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now(), onupdate=func.now())

    profile = relationship("StudentProfile", back_populates="session", uselist=False)
    courses = relationship("StudentCourse", back_populates="session")
    exceptions = relationship("PolicyException", back_populates="session")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("student_sessions.session_id"))
    school = Column(String(100))
    program_code = Column(String(50))
    enrollment_status = Column(String(50))
    student_type = Column(String(50))
    financial_aid_type = Column(String(50))
    graduation_year = Column(Integer)
    graduation_semester = Column(String(20))

    session = relationship("StudentSession", back_populates="profile")


class StudentCourse(Base):
    __tablename__ = "student_courses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("student_sessions.session_id"))
    course_code = Column(String(20))
    semester_taken = Column(String(20))
    status = Column(String(20))
    grade = Column(String(5))
    credits = Column(Numeric(4, 2))
    source = Column(String(50))

    session = relationship("StudentSession", back_populates="courses")


class EnrollmentStatusRule(Base):
    __tablename__ = "enrollment_status_rules"

    id = Column(Integer, primary_key=True, index=True)
    status_name = Column(String(50), nullable=False)
    min_credits = Column(Numeric(4, 2), nullable=False)
    max_credits = Column(Numeric(4, 2))
    description = Column(Text)
    is_default = Column(Boolean, default=False)


class FinancialAidConstraint(Base):
    __tablename__ = "financial_aid_constraints"

    id = Column(Integer, primary_key=True, index=True)
    aid_type = Column(String(50), nullable=False)
    min_credits_required = Column(Numeric(4, 2))
    min_status_required = Column(String(50))
    warning_message = Column(Text)
    block_underload = Column(Boolean, default=False)
    allow_exception_process = Column(Boolean, default=False)


class AcademicPolicy(Base):
    __tablename__ = "academic_policies"

    id = Column(Integer, primary_key=True, index=True)
    policy_type = Column(String(50), nullable=False)
    policy_code = Column(String(50))
    description = Column(Text, nullable=False)
    rule_logic = Column(JSON)
    applies_to_student_types = Column(JSON)
    applies_to_programs = Column(JSON)
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    is_hardcoded = Column(Boolean, default=False)

    exceptions = relationship("PolicyException", back_populates="policy")


class PolicyException(Base):
    __tablename__ = "policy_exceptions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("student_sessions.session_id"))
    policy_id = Column(Integer, ForeignKey("academic_policies.id"))
    reason = Column(Text)
    approved_by = Column(String(100))
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    session = relationship("StudentSession", back_populates="exceptions")
    policy = relationship("AcademicPolicy", back_populates="exceptions")
