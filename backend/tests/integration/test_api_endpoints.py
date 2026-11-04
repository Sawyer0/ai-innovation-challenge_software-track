"""
Integration tests for API endpoints with test database.

Tests use FastAPI TestClient with real (test) database.
External APIs are mocked.
"""

from io import BytesIO
from typing import Any, ClassVar

import pytest

from app import models
from app.infrastructure.ai import NoProviderConfiguredError


@pytest.mark.integration
class TestSessionEndpoints:
    """Test session CRUD operations."""

    def test_create_session(self, client):
        """POST /api/session should create new session with UUID."""
        response = client.post("/api/session")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) == 36  # UUID v4 format
        assert "created_at" in data

    def test_get_session_not_found(self, client):
        """GET /api/session/{id} should 404 for non-existent session."""
        response = client.get("/api/session/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_session_with_profile_and_courses(self, client):
        """GET /api/session/{id} should return session with related data."""
        # Create session
        create_resp = client.post("/api/session")
        session_id = create_resp.json()["session_id"]

        # Set profile
        profile_resp = client.post(
            f"/api/session/{session_id}/profile",
            json={"school": "BMCC", "program_code": "CSC-AS", "enrollment_status": "full-time"},
        )
        assert profile_resp.status_code == 200

        # Add course
        course_resp = client.post(
            f"/api/session/{session_id}/courses",
            json={
                "course_code": "MAT 157",
                "status": "completed",
                "semester_taken": "Fall 2023",
                "grade": "A",
                "credits": 4,
            },
        )
        assert course_resp.status_code == 200

        # Get full session
        get_resp = client.get(f"/api/session/{session_id}")
        assert get_resp.status_code == 200

        data = get_resp.json()
        assert data["session_id"] == session_id
        assert data["profile"]["program_code"] == "CSC-AS"
        assert len(data["courses"]) == 1
        assert data["courses"][0]["course_code"] == "MAT 157"

    def test_set_profile_creates_if_not_exists(self, client):
        """POST /api/session/{id}/profile should create profile if missing."""
        session_id = client.post("/api/session").json()["session_id"]

        response = client.post(
            f"/api/session/{session_id}/profile", json={"school": "BMCC", "program_code": "CSC-AS"}
        )

        assert response.status_code == 200
        assert response.json()["program_code"] == "CSC-AS"

    def test_set_profile_updates_existing(self, client):
        """POST /api/session/{id}/profile should update existing profile."""
        session_id = client.post("/api/session").json()["session_id"]

        # Create initial profile
        client.post(f"/api/session/{session_id}/profile", json={"program_code": "CSC-AS"})

        # Update it
        response = client.post(
            f"/api/session/{session_id}/profile",
            json={"program_code": "ACC-AAS", "enrollment_status": "half-time"},
        )

        assert response.status_code == 200
        assert response.json()["program_code"] == "ACC-AAS"
        assert response.json()["enrollment_status"] == "half-time"


@pytest.mark.integration
class TestSessionStatus:
    def test_status_reports_valid_session(self, client):
        session_id = client.post("/api/session").json()["session_id"]

        response = client.get(f"/api/session/{session_id}/status")

        assert response.status_code == 200
        assert response.json()["is_valid"] is True

    def test_status_404_for_unknown_session(self, client):
        assert client.get("/api/session/nope/status").status_code == 404


@pytest.mark.integration
class TestCourseEndpoints:
    """Test course catalog endpoints."""

    def test_list_courses_paginated(self, client):
        """GET /api/courses should return paginated list."""
        response = client.get("/api/courses?skip=0&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10

    def test_get_course_by_code(self, client, db, sample_courses):
        """GET /api/courses/{code} should return course details."""
        # Seed a course
        from app import models

        course = models.Course(**sample_courses[0])
        db.add(course)
        db.commit()

        response = client.get("/api/courses/MAT 157")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "MAT 157"
        assert data["title"] == "College Algebra and Trigonometry"

    def test_get_course_not_found(self, client):
        """GET /api/courses/{code} should 404 for unknown course."""
        response = client.get("/api/courses/INVALID 999")

        assert response.status_code == 404


@pytest.mark.integration
class TestProgramEndpoints:
    """Test program endpoints."""

    def test_list_programs(self, client):
        """GET /api/programs should return all programs."""
        response = client.get("/api/programs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_program_by_code(self, client, db):
        """GET /api/programs/{code} should return program with requirements."""
        from app import models

        # Seed program
        program = models.Program(program_code="CSC-AS", name="Computer Science", degree="A.S.")
        db.add(program)
        db.commit()
        db.refresh(program)

        # Add requirements
        req = models.ProgramRequirement(
            program_id=program.id,
            course_code="MAT 206",
            semester_year="Year 1",
            semester_term="Fall",
            is_required=True,
        )
        db.add(req)
        db.commit()

        response = client.get("/api/programs/CSC-AS")

        assert response.status_code == 200
        data = response.json()
        assert data["program_code"] == "CSC-AS"


def _plan(*courses: tuple[str, float]) -> dict:
    return {
        "advisor_message": "Here is a plan.",
        "recommended_courses": [
            {
                "course_code": code,
                "course_title": code,
                "credits": credits,
                "requirement_satisfied": "Required",
                "compliance_status": "compliant",
                "compliance_note": None,
                "career_rationale": "Builds toward your goal.",
                "why_now": "Prerequisites are complete.",
            }
            for code, credits in courses
        ],
    }


def _seed_mat_sequence(db) -> None:
    """CSC-AS requires MAT 206, which needs MAT 157."""
    mat157 = models.Course(code="MAT 157", title="College Algebra", credits=4)
    mat206 = models.Course(code="MAT 206", title="Precalculus", credits=4)
    program = models.Program(program_code="CSC-AS", name="Computer Science", degree="A.S.")
    db.add_all([mat157, mat206, program])
    db.commit()
    db.add_all(
        [
            models.CoursePrerequisite(
                course_id=mat206.id, prerequisite_course_code="MAT 157", logic_group=1
            ),
            models.ProgramRequirement(
                program_id=program.id, course_code="MAT 206", is_required=True
            ),
        ]
    )
    db.commit()


def _session_with_profile(client, **profile) -> str:
    session_id = client.post("/api/session").json()["session_id"]
    body = {"school": "BMCC", "program_code": "CSC-AS", "enrollment_status": "full-time"}
    body.update(profile)
    assert client.post(f"/api/session/{session_id}/profile", json=body).status_code == 200
    return session_id


@pytest.mark.integration
class TestAdvisementEndpoints:
    """Advisement flow with fake AI providers."""

    def test_get_eligible_courses(self, client, db):
        _seed_mat_sequence(db)
        session_id = _session_with_profile(client)
        client.post(
            f"/api/session/{session_id}/courses",
            json={"course_code": "MAT 157", "status": "completed", "credits": 4},
        )

        response = client.get(f"/api/session/{session_id}/advisement/eligible")

        assert response.status_code == 200
        assert response.json()["eligible_courses"] == ["MAT 206"]

    def test_in_progress_courses_count_toward_prerequisites(self, client, db):
        _seed_mat_sequence(db)
        session_id = _session_with_profile(client)
        client.post(
            f"/api/session/{session_id}/courses",
            json={"course_code": "MAT 157", "status": "in-progress", "credits": 4},
        )

        response = client.get(f"/api/session/{session_id}/advisement/eligible")

        assert response.json()["eligible_courses"] == ["MAT 206"]

    def test_eligible_requires_program(self, client):
        session_id = client.post("/api/session").json()["session_id"]

        response = client.get(f"/api/session/{session_id}/advisement/eligible")

        assert response.status_code == 400
        assert "Traceback" not in response.text

    def test_advisement_endpoint(self, client, db, ai_providers):
        _seed_mat_sequence(db)
        ai_providers.primary.queue(_plan(("MAT 206", 4)))
        session_id = _session_with_profile(client)
        client.post(
            f"/api/session/{session_id}/courses",
            json={"course_code": "MAT 157", "status": "completed", "credits": 4},
        )

        response = client.post(
            f"/api/session/{session_id}/advisement", json={"message": "What should I take next?"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["compliance_cleared"] is True
        assert [c["course_code"] for c in data["recommended_courses"]] == ["MAT 206"]
        assert data["total_planned_credits"] == 4.0
        assert "Always confirm" in data["disclaimer"]
        assert "- MAT 206: Precalculus" in ai_providers.primary.calls[0]["prompt"]

    def test_advisement_returns_502_when_ai_is_unavailable(self, client):
        session_id = _session_with_profile(client)

        response = client.post(f"/api/session/{session_id}/advisement", json={"message": "Help?"})

        assert response.status_code == 502

    def test_advisement_returns_503_without_any_api_key(self, client, monkeypatch):
        def no_providers():
            raise NoProviderConfiguredError()

        monkeypatch.setattr("app.services.ai_service.get_providers", no_providers)
        session_id = _session_with_profile(client)

        response = client.post(f"/api/session/{session_id}/advisement", json={"message": "?"})

        assert response.status_code == 503
        assert "GROQ_API_KEY" in response.json()["detail"]

    def test_advisement_requires_profile(self, client):
        session_id = client.post("/api/session").json()["session_id"]

        response = client.post(f"/api/session/{session_id}/advisement", json={"message": "Help?"})

        assert response.status_code == 400
        assert "profile not set" in response.json()["detail"].lower()


@pytest.mark.integration
class TestComplianceGuardrails:
    """Deterministic blocks run before the AI is ever called."""

    def _plan_courses(self, client, session_id: str, *courses: tuple[str, int]) -> None:
        for code, credits in courses:
            client.post(
                f"/api/session/{session_id}/courses",
                json={"course_code": code, "status": "planned", "credits": credits},
            )

    def test_tap_underload_is_blocked_before_ai(self, client, ai_providers):
        session_id = _session_with_profile(client, financial_aid_type="tap")
        self._plan_courses(client, session_id, ("ENG 101", 3), ("MAT 157", 4))

        response = client.post(f"/api/session/{session_id}/advisement", json={"message": "?"})

        assert response.status_code == 422
        assert response.json()["detail"]["type"] == "compliance_violation"
        assert ai_providers.primary.calls == []

    def test_f1_student_below_full_time_is_blocked(self, client, ai_providers):
        session_id = _session_with_profile(client, student_type="international")
        self._plan_courses(client, session_id, ("ENG 101", 3), ("MAT 157", 4))

        response = client.post(f"/api/session/{session_id}/advisement", json={"message": "?"})

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["type"] == "visa_compliance_violation"
        assert "12 credits" in detail["message"]
        assert ai_providers.primary.calls == []

    def test_f1_student_with_two_online_courses_is_blocked(self, client, db):
        db.add_all(
            [
                models.Course(code=f"CSC 10{i}", title="x", credits=3, instruction_mode="Online")
                for i in range(2)
            ]
        )
        db.commit()
        session_id = _session_with_profile(client, student_type="international")
        self._plan_courses(
            client, session_id, ("CSC 100", 3), ("CSC 101", 3), ("ENG 101", 3), ("MAT 157", 4)
        )

        response = client.post(f"/api/session/{session_id}/advisement", json={"message": "?"})

        assert response.status_code == 422
        assert "online or hybrid" in response.json()["detail"]["message"]

    def test_pell_proration_reflects_recommended_credits(self, client, ai_providers):
        ai_providers.primary.queue(_plan(("ENG 101", 3), ("MAT 157", 4), ("CSC 101", 2)))
        session_id = _session_with_profile(client, financial_aid_type="pell")

        response = client.post(f"/api/session/{session_id}/advisement", json={"message": "?"})

        assert response.status_code == 200
        proration = response.json()["pell_proration"]
        assert proration["planned_credits"] == 9.0
        assert proration["percentage_display"] == "75%"


@pytest.mark.integration
class TestTranscriptEndpoints:
    """Transcript upload: AI parses, the student reviews, then courses are bulk-saved."""

    TRANSCRIPT: ClassVar[dict[str, Any]] = {
        "profile": {"school": "BMCC", "program_code": "CSC-AS"},
        "courses": [
            {
                "course_code": "MAT 206",
                "course_title": "Precalculus",
                "semester_taken": "Fall 2023",
                "status": "completed",
                "grade": "B+",
                "credits": 4,
            },
            {"course_code": None, "course_title": "Unreadable row"},
        ],
    }

    def test_upload_parses_without_saving(self, client, ai_providers):
        ai_providers.primary.queue(self.TRANSCRIPT)
        session_id = client.post("/api/session").json()["session_id"]

        response = client.post(
            f"/api/session/{session_id}/transcript",
            files={"file": ("transcript.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["program_code"] == "CSC-AS"
        assert [c["course_code"] for c in data["courses"]] == ["MAT 206"]
        assert client.get(f"/api/session/{session_id}").json()["courses"] == []

    def test_bulk_save_skips_duplicates(self, client):
        session_id = client.post("/api/session").json()["session_id"]
        course = {"course_code": "MAT 206", "semester_taken": "Fall 2023", "status": "completed"}

        first = client.post(f"/api/session/{session_id}/courses/bulk", json=[course])
        second = client.post(f"/api/session/{session_id}/courses/bulk", json=[course])

        assert first.json() == {"saved": 1, "total": 1}
        assert second.json() == {"saved": 0, "total": 1}
        courses = client.get(f"/api/session/{session_id}").json()["courses"]
        assert [(c["course_code"], c["source"]) for c in courses] == [("MAT 206", "transcript")]

    def test_unsupported_file_type_is_rejected(self, client, ai_providers):
        session_id = client.post("/api/session").json()["session_id"]

        response = client.post(
            f"/api/session/{session_id}/transcript",
            files={"file": ("notes.txt", BytesIO(b"hello"), "text/plain")},
        )

        assert response.status_code == 400
        assert ai_providers.primary.calls == []

    def test_upload_returns_502_when_both_providers_fail(self, client):
        session_id = client.post("/api/session").json()["session_id"]

        response = client.post(
            f"/api/session/{session_id}/transcript",
            files={"file": ("t.png", BytesIO(b"fake"), "image/png")},
        )

        assert response.status_code == 502

    def test_upload_requires_valid_session(self, client):
        response = client.post(
            "/api/session/invalid-session/transcript",
            files={"file": ("test.png", BytesIO(b"fake"), "image/png")},
        )

        assert response.status_code == 404
