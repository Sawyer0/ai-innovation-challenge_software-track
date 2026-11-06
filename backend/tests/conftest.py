"""
Shared fixtures for all tests.

Follows Google testing best practices:
- Fast fixtures with function scope for isolation
- Mock external services (no real API calls)
- Test database separate from dev/prod
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.rate_limit import reset_ai_rate_limits
from app.main import app

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "bmcc-catalog.json"

# In-memory database shared across connections, so no files are left behind.
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class FakeProvider:
    """An LLMProvider that replays queued replies and records every call.

    With nothing queued it raises, like a provider that is down. A queued Exception
    is raised instead of returned. ``reads_pdf=False`` behaves like Groq: PDFs reach it
    as text (``complete``) or page images (``read_images``).
    """

    def __init__(self, name: str, *, reads_pdf: bool = True, max_images: int = 3) -> None:
        self.name = name
        self.reads_pdf = reads_pdf
        self.max_images_per_request = max_images
        self.replies: list[str | Exception] = []
        self.calls: list[dict[str, Any]] = []

    def queue(self, *replies: str | dict[str, Any] | list[Any] | Exception) -> None:
        self.replies.extend(r if isinstance(r, str | Exception) else json.dumps(r) for r in replies)

    def _next(self, **call: Any) -> str:
        self.calls.append(call)
        if not self.replies:
            raise RuntimeError(f"{self.name} unavailable (no reply queued)")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        return self._next(system=system, prompt=prompt)

    async def read_document(
        self, system: str, prompt: str, data: bytes, mime_type: str, *, max_tokens: int
    ) -> str:
        return self._next(system=system, prompt=prompt, data=data, mime_type=mime_type)

    async def read_images(
        self, system: str, prompt: str, images: Any, mime_type: str, *, max_tokens: int
    ) -> str:
        return self._next(system=system, prompt=prompt, images=list(images), mime_type=mime_type)


@pytest.fixture(autouse=True)
def ai_providers(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Swap the provider chain for two fakes so no test can reach a real API."""
    primary, fallback = FakeProvider("primary"), FakeProvider("fallback")
    for module in ("app.services.ai_service", "app.parsers.transcript_parser"):
        monkeypatch.setattr(f"{module}.get_providers", lambda: [primary, fallback])
    return SimpleNamespace(primary=primary, fallback=fallback)


@pytest.fixture(scope="function")
def db():
    """
    Fresh database for each test function.
    Creates tables before test, drops after.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # Seed enrollment status rules
    from app import models

    default_rules = [
        models.EnrollmentStatusRule(
            status_name="full-time",
            min_credits=12,
            max_credits=18,
            description="Full-time student (12-18 credits)",
        ),
        models.EnrollmentStatusRule(
            status_name="half-time",
            min_credits=6,
            max_credits=11,
            description="Half-time student (6-11 credits)",
        ),
        models.EnrollmentStatusRule(
            status_name="less-than-half-time",
            min_credits=0,
            max_credits=5,
            description="Less than half-time (0-5 credits)",
        ),
    ]
    for rule in default_rules:
        session.add(rule)

    # Seed financial aid constraints
    aid_constraints = [
        models.FinancialAidConstraint(
            aid_type="pell",
            min_credits_required=6,
            min_status_required="half-time",
            warning_message="Dropping below 6 credits may affect your Pell Grant eligibility.",
            block_underload=True,
            allow_exception_process=False,
        ),
        models.FinancialAidConstraint(
            aid_type="tap",
            min_credits_required=12,
            min_status_required="full-time",
            warning_message="TAP requires full-time enrollment (12+ credits).",
            block_underload=True,
            allow_exception_process=False,
        ),
    ]
    # Mirrors data/rules.json: Pell and TAP block an underload, Excelsior only advises.
    aid_constraints.append(
        models.FinancialAidConstraint(
            aid_type="excelsior",
            min_credits_required=15,
            min_status_required="full-time",
            warning_message="Excelsior recommends 15 credits per semester.",
            block_underload=False,
            allow_exception_process=True,
        )
    )
    for constraint in aid_constraints:
        session.add(constraint)

    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_ai_rate_limits():
    """Per-IP AI limits are process-wide; start every test with a clean window."""
    reset_ai_rate_limits()
    yield
    reset_ai_rate_limits()


@pytest.fixture(scope="function")
def client(db):
    """
    TestClient with overridden DB dependency.
    Uses the test database session.
    """

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]


@pytest.fixture
def mock_profile():
    """
    Standard student profile for testing.
    """
    from unittest.mock import Mock

    return Mock(
        enrollment_status="full-time",
        student_type="regular",
        financial_aid_type="pell",
        program_code="CSC-AS",
        graduation_semester="Spring",
        graduation_year=2026,
        classification="freshman",
        academic_standing="good standing",
        career_goal="robotics engineer",
    )


@pytest.fixture
def sample_courses():
    """
    Sample course data for tests.
    """
    return [
        {
            "code": "MAT 157",
            "title": "College Algebra and Trigonometry",
            "credits": 4.0,
            "subject": "MAT",
            "department": "Mathematics",
            "hegis_code": "5617.00",
        },
        {
            "code": "MAT 206",
            "title": "Precalculus",
            "credits": 4.0,
            "subject": "MAT",
            "department": "Mathematics",
            "hegis_code": "5617.00",
        },
        {
            "code": "ENG 101",
            "title": "English Composition",
            "credits": 3.0,
            "subject": "ENG",
            "department": "English",
            "hegis_code": "1501.00",
        },
        {
            "code": "CSC 103",
            "title": "Introduction to Computing",
            "credits": 3.0,
            "subject": "CSC",
            "department": "Computer Science",
            "hegis_code": "5101.00",
        },
    ]


@pytest.fixture
def sample_prerequisites():
    """
    Sample prerequisite relationships for tests.
    """
    return [
        {
            "course_code": "MAT 206",
            "prerequisite_course_code": "MAT 157",
            "is_corequisite": False,
            "logic_group": 1,
        },
        {
            "course_code": "CSC 201",
            "prerequisite_course_code": "CSC 103",
            "is_corequisite": False,
            "logic_group": 1,
        },
    ]


@pytest.fixture(scope="function")
def full_catalog(db):
    """
    Loads the complete BMCC catalog with all courses, prerequisites, and programs.
    Use for data quality tests that need full catalog data.
    """
    from decimal import Decimal

    from app.models import Course, CoursePrerequisite, Program, ProgramRequirement

    catalog_path = CATALOG_PATH
    if not catalog_path.exists():
        pytest.skip("data/bmcc-catalog.json not found - cannot load full catalog")

    # Load catalog JSON
    with open(catalog_path, encoding="utf-8") as f:
        catalog_data = json.load(f)

    courses_data = catalog_data.get("courses", [])
    programs_data = catalog_data.get("programs", [])

    # Insert courses
    course_map = {}  # code -> Course object
    seen_codes = set()

    for c_data in courses_data:
        code = c_data.get("code")
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        try:
            credit_val = Decimal(str(c_data.get("credits", 0)))
        except Exception:
            credit_val = Decimal(0)

        course = Course(
            code=code,
            title=c_data.get("title", ""),
            long_name=c_data.get("long_name"),
            description=c_data.get("description"),
            credits=credit_val,
            subject=c_data.get("subject"),
            department=c_data.get("department"),
            hegis_code=c_data.get("hegis_code"),
            typically_offered=c_data.get("typically_offered"),
        )
        db.add(course)
        course_map[code] = course

    db.commit()

    # Refresh to get course IDs
    for course in course_map.values():
        db.refresh(course)

    # Insert prerequisites
    prereq_count = 0
    for c_data in courses_data:
        code = c_data.get("code")
        prereqs = c_data.get("prerequisites", [])

        course = course_map.get(code)
        if not course or not prereqs:
            continue

        for prereq in prereqs:
            text = (
                prereq.get("text", "").strip() if isinstance(prereq, dict) else str(prereq).strip()
            )
            if not text:
                continue

            cp = CoursePrerequisite(course_id=course.id, is_corequisite=False, notes=text)
            db.add(cp)
            prereq_count += 1

    db.commit()

    # Insert programs
    seen_programs = set()
    for p_data in programs_data:
        prog_code = p_data.get("programCode")
        if not prog_code or prog_code in seen_programs:
            continue
        seen_programs.add(prog_code)

        program = Program(
            program_code=prog_code,
            name=p_data.get("name", ""),
            long_name=p_data.get("name"),
            description=p_data.get("description"),
            degree=p_data.get("degree"),
            department=p_data.get("department"),
            hegis_code=p_data.get("hegisCode"),
        )
        db.add(program)
        db.commit()
        db.refresh(program)

        # Insert program requirements
        semesters = p_data.get("semesters", [])
        for sem in semesters:
            # Required courses
            for req_code in sem.get("required_courses", []):
                pr = ProgramRequirement(
                    program_id=program.id,
                    course_code=req_code,
                    semester_year=sem.get("year", ""),
                    semester_term=sem.get("semester", ""),
                    is_required=True,
                )
                db.add(pr)

            # Elective groups
            for egroup in sem.get("elective_groups", []):
                for elect_code in egroup.get("courses", []):
                    pr = ProgramRequirement(
                        program_id=program.id,
                        course_code=elect_code,
                        semester_year=sem.get("year", ""),
                        semester_term=sem.get("semester", ""),
                        is_required=False,
                        elective_group=egroup.get("name"),
                    )
                    db.add(pr)

        db.commit()

    yield {
        "courses": len(course_map),
        "prerequisites": prereq_count,
        "programs": len(seen_programs),
    }

    # Cleanup happens automatically when db fixture tears down
