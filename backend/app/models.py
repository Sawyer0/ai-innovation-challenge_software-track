from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    long_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    credits: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    subject: Mapped[str | None] = mapped_column(String(50))
    department: Mapped[str | None] = mapped_column(String(100))
    hegis_code: Mapped[str | None] = mapped_column(String(20))
    typically_offered: Mapped[str | None] = mapped_column(String(100))
    instruction_mode: Mapped[str | None] = mapped_column(
        String(50)
    )  # "In Person", "Online", "Hybrid"
    raw_data: Mapped[Any | None] = mapped_column(JSON)

    prerequisites: Mapped[list["CoursePrerequisite"]] = relationship(back_populates="course")


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("courses.id"))
    prerequisite_course_code: Mapped[str | None] = mapped_column(String(20))
    is_corequisite: Mapped[bool | None] = mapped_column(Boolean, default=False)
    logic_group: Mapped[int | None] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text)
    minimum_grade: Mapped[str | None] = mapped_column(
        String(2), default="C"
    )  # "C" or better required by default

    # New indexing columns for non-course attributes
    is_attribute: Mapped[bool | None] = mapped_column(Boolean, default=False)
    attribute_name: Mapped[str | None] = mapped_column(String(50))
    attribute_value: Mapped[str | None] = mapped_column(String(50))

    course: Mapped["Course | None"] = relationship(back_populates="prerequisites")


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    program_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    long_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    degree: Mapped[str | None] = mapped_column(String(50))
    department: Mapped[str | None] = mapped_column(String(100))
    hegis_code: Mapped[str | None] = mapped_column(String(20))
    raw_data: Mapped[Any | None] = mapped_column(JSON)

    requirements: Mapped[list["ProgramRequirement"]] = relationship(back_populates="program")


class ProgramRequirement(Base):
    __tablename__ = "program_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    program_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("programs.id"))
    course_code: Mapped[str | None] = mapped_column(String(20))
    semester_year: Mapped[str | None] = mapped_column(String(20))
    semester_term: Mapped[str | None] = mapped_column(String(20))
    is_required: Mapped[bool | None] = mapped_column(Boolean, default=True)
    elective_group: Mapped[str | None] = mapped_column(String(50))
    min_credits: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    # New indexing columns for wildcard patterns (e.g., "ART *")
    is_wildcard: Mapped[bool | None] = mapped_column(Boolean, default=False)
    wildcard_subject: Mapped[str | None] = mapped_column(String(20))
    wildcard_level: Mapped[str | None] = mapped_column(String(10))

    program: Mapped["Program | None"] = relationship(back_populates="requirements")


class StudentSession(Base):
    __tablename__ = "student_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=func.now())
    last_activity: Mapped[datetime | None] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # 30-day session expiry

    profile: Mapped["StudentProfile | None"] = relationship(back_populates="session")
    courses: Mapped[list["StudentCourse"]] = relationship(back_populates="session")
    exceptions: Mapped[list["PolicyException"]] = relationship(back_populates="session")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("student_sessions.session_id")
    )
    school: Mapped[str | None] = mapped_column(String(100))
    program_code: Mapped[str | None] = mapped_column(String(50))
    enrollment_status: Mapped[str | None] = mapped_column(String(50))  # Full-time, Part-time
    student_type: Mapped[str | None] = mapped_column(
        String(50)
    )  # Continuing, Transfer, International
    classification: Mapped[str | None] = mapped_column(
        String(50)
    )  # Freshman, Sophomore, Junior, Senior
    academic_standing: Mapped[str | None] = mapped_column(
        String(50)
    )  # Good Standing, Probation, Dismissed
    financial_aid_type: Mapped[str | None] = mapped_column(String(50))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    graduation_semester: Mapped[str | None] = mapped_column(String(20))
    career_goal: Mapped[str | None] = mapped_column(Text)

    session: Mapped["StudentSession | None"] = relationship(back_populates="profile")


class StudentCourse(Base):
    __tablename__ = "student_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("student_sessions.session_id")
    )
    course_code: Mapped[str | None] = mapped_column(String(20))
    semester_taken: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20))
    grade: Mapped[str | None] = mapped_column(String(5))
    credits: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    source: Mapped[str | None] = mapped_column(String(50))

    session: Mapped["StudentSession | None"] = relationship(back_populates="courses")


class EnrollmentStatusRule(Base):
    __tablename__ = "enrollment_status_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status_name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_credits: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    max_credits: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool | None] = mapped_column(Boolean, default=False)


class FinancialAidConstraint(Base):
    __tablename__ = "financial_aid_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    aid_type: Mapped[str] = mapped_column(String(50), nullable=False)
    min_credits_required: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    min_status_required: Mapped[str | None] = mapped_column(String(50))
    warning_message: Mapped[str | None] = mapped_column(Text)
    block_underload: Mapped[bool | None] = mapped_column(Boolean, default=False)
    allow_exception_process: Mapped[bool | None] = mapped_column(Boolean, default=False)


class AcademicPolicy(Base):
    __tablename__ = "academic_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rule_logic: Mapped[Any | None] = mapped_column(JSON)
    applies_to_student_types: Mapped[Any | None] = mapped_column(
        JSON
    )  # entry types: Continuing, Transfer, etc.
    applies_to_classifications: Mapped[Any | None] = mapped_column(
        JSON
    )  # freshman, sophomore, etc.
    applies_to_academic_standings: Mapped[Any | None] = mapped_column(
        JSON
    )  # Good Standing, Probation, etc.
    applies_to_programs: Mapped[Any | None] = mapped_column(JSON)
    priority: Mapped[int | None] = mapped_column(Integer, default=100)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    is_hardcoded: Mapped[bool | None] = mapped_column(Boolean, default=False)

    exceptions: Mapped[list["PolicyException"]] = relationship(back_populates="policy")


class PolicyException(Base):
    __tablename__ = "policy_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("student_sessions.session_id")
    )
    policy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("academic_policies.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(String(100))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)

    session: Mapped["StudentSession | None"] = relationship(back_populates="exceptions")
    policy: Mapped["AcademicPolicy | None"] = relationship(back_populates="exceptions")
