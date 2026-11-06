"""
End-to-end tests for complete user journeys, mirroring what the React app does:
create session -> upload transcript -> review and save courses -> set profile
-> get advisement. AI providers are the fakes from conftest.
"""

import uuid
from io import BytesIO

import pytest

from app import models

TRANSCRIPT = {
    "profile": {"school": "BMCC", "program_code": "CSC-AS", "classification": "freshman"},
    "courses": [
        {
            "course_code": "MAT 157",
            "semester_taken": "Spring 2025",
            "status": "completed",
            "grade": "A",
            "credits": 4,
        },
        {
            "course_code": "ENG 101",
            "semester_taken": "Spring 2025",
            "status": "completed",
            "grade": "B+",
            "credits": 3,
        },
    ],
}

PLAN = {
    "advisor_message": "With MAT 157 done, Precalculus keeps you on the engineering track.",
    "recommended_courses": [
        {
            "course_code": code,
            "course_title": title,
            "credits": credits,
            "requirement_satisfied": "Required",
            "compliance_status": "compliant",
            "compliance_note": None,
            "career_rationale": "Builds toward robotics.",
            "why_now": "Prerequisites are complete.",
        }
        for code, title, credits in [
            ("MAT 206", "Precalculus", 4),
            ("ENG 201", "Composition II", 3),
            ("CSC 101", "Principles in IT", 3),
            ("SCI 120", "Lab Science", 2),
        ]
    ],
}


@pytest.fixture
def csc_program(db):
    """CSC-AS requires MAT 206 (prereq MAT 157) and ENG 201 (prereq ENG 101)."""
    courses = {
        code: models.Course(code=code, title=title, credits=credits)
        for code, title, credits in [
            ("MAT 157", "College Algebra", 4),
            ("MAT 206", "Precalculus", 4),
            ("ENG 101", "Composition I", 3),
            ("ENG 201", "Composition II", 3),
        ]
    }
    program = models.Program(program_code="CSC-AS", name="Computer Science", degree="A.S.")
    db.add_all([*courses.values(), program])
    db.commit()
    db.add_all(
        [
            models.CoursePrerequisite(
                course_id=courses["MAT 206"].id, prerequisite_course_code="MAT 157"
            ),
            models.CoursePrerequisite(
                course_id=courses["ENG 201"].id, prerequisite_course_code="ENG 101"
            ),
            models.ProgramRequirement(program_id=program.id, course_code="MAT 206"),
            models.ProgramRequirement(program_id=program.id, course_code="ENG 201"),
        ]
    )
    db.commit()


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteStudentWorkflow:
    def test_transcript_to_personalized_plan(self, client, csc_program, ai_providers):
        ai_providers.primary.queue(TRANSCRIPT, PLAN)

        session_id = client.post("/api/session").json()["session_id"]

        parsed = client.post(
            f"/api/session/{session_id}/transcript",
            files={"file": ("transcript.png", BytesIO(b"fake image"), "image/png")},
        )
        assert parsed.status_code == 200
        courses = parsed.json()["courses"]
        assert [c["course_code"] for c in courses] == ["MAT 157", "ENG 101"]

        saved = client.post(f"/api/session/{session_id}/courses/bulk", json=courses)
        assert saved.json() == {"saved": 2, "total": 2}

        profile = {
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "full-time",
            "financial_aid_type": "pell",
            "career_goal": "robotics engineer",
            "graduation_year": 2027,
            "graduation_semester": "Spring",
        }
        assert client.post(f"/api/session/{session_id}/profile", json=profile).status_code == 200

        eligible = client.get(f"/api/session/{session_id}/advisement/eligible").json()
        assert eligible["eligible_courses"] == ["MAT 206", "ENG 201"]

        resp = client.post(
            f"/api/session/{session_id}/advisement",
            json={"message": "What should I take next semester?"},
        )
        assert resp.status_code == 200
        plan = resp.json()
        assert plan["recommended_courses"][0]["course_code"] == "MAT 206"
        assert plan["total_planned_credits"] == 12.0
        assert plan["pell_proration"]["percentage_display"] == "100%"

        advisement_prompt = ai_providers.primary.calls[1]["prompt"]
        assert "MAT 157, ENG 101" in advisement_prompt or "ENG 101, MAT 157" in advisement_prompt
        assert "robotics engineer" in advisement_prompt

        session = client.get(f"/api/session/{session_id}").json()
        assert session["profile"]["program_code"] == "CSC-AS"
        assert len(session["courses"]) == 2

    def test_student_can_manually_add_courses(self, client, csc_program, ai_providers):
        ai_providers.primary.queue(PLAN)
        session_id = client.post("/api/session").json()["session_id"]
        client.post(
            f"/api/session/{session_id}/profile",
            json={"school": "BMCC", "program_code": "CSC-AS", "enrollment_status": "full-time"},
        )

        for code, credits in [("MAT 157", 4), ("ENG 101", 3)]:
            resp = client.post(
                f"/api/session/{session_id}/courses",
                json={"course_code": code, "status": "completed", "credits": credits},
            )
            assert resp.status_code == 200

        resp = client.post(
            f"/api/session/{session_id}/advisement", json={"message": "What should I take?"}
        )
        assert resp.status_code == 200
        assert len(resp.json()["recommended_courses"]) == 4

    def test_tap_student_gets_elective_warning(self, client, csc_program, ai_providers):
        ai_providers.primary.queue(PLAN)
        session_id = client.post("/api/session").json()["session_id"]
        client.post(
            f"/api/session/{session_id}/profile",
            json={
                "program_code": "CSC-AS",
                "enrollment_status": "full-time",
                "financial_aid_type": "tap",
            },
        )

        plan = client.post(f"/api/session/{session_id}/advisement", json={"message": "?"}).json()

        status = {c["course_code"]: c["compliance_status"] for c in plan["recommended_courses"]}
        # Required courses are TAP-allowable; courses outside the program are flagged.
        assert status["MAT 206"] == "compliant"
        assert status["CSC 101"] == "warning"


@pytest.mark.e2e
@pytest.mark.slow
class TestErrorHandlingWorkflows:
    def test_invalid_session_id_returns_404(self, client):
        assert client.get("/api/session/invalid-uuid").status_code == 404
        assert (
            client.post("/api/session/invalid-uuid/profile", json={"school": "BMCC"}).status_code
            == 404
        )
        assert (
            client.post(
                "/api/session/invalid-uuid/courses", json={"course_code": "MAT 101"}
            ).status_code
            == 404
        )

    def test_advisement_without_profile_returns_error(self, client):
        session_id = client.post("/api/session").json()["session_id"]

        resp = client.post(f"/api/session/{session_id}/advisement", json={"message": "Help?"})

        assert resp.status_code == 400
        assert "profile" in resp.json()["detail"].lower()

    def test_cannot_add_duplicate_courses(self, client):
        session_id = client.post("/api/session").json()["session_id"]

        resp = client.post(
            f"/api/session/{session_id}/courses",
            json={"course_code": "MAT 206", "status": "completed", "credits": 4},
        )
        assert resp.status_code == 200

        resp = client.post(
            f"/api/session/{session_id}/courses",
            json={"course_code": "MAT 206", "status": "in-progress", "credits": 4},
        )
        assert resp.status_code in [200, 409]


PROFILE = {
    "school": "BMCC",
    "program_code": "CSC-AS",
    "enrollment_status": "full-time",
    "financial_aid_type": "pell",
    "career_goal": "robotics engineer",
}


@pytest.mark.e2e
@pytest.mark.slow
class TestSessionsUnknownToThisInstance:
    """On Vercel each instance has its own session store, so a session id the browser
    holds is often unknown to the instance that handles the next request."""

    def test_upload_with_an_unknown_session_id_succeeds(self, client, ai_providers):
        ai_providers.primary.queue(TRANSCRIPT)

        response = client.post(
            f"/api/session/{uuid.uuid4()}/transcript",
            files={"file": ("JTTranscript.png", BytesIO(b"fake image"), "image/png")},
        )

        assert response.status_code == 200
        assert [c["course_code"] for c in response.json()["courses"]] == ["MAT 157", "ENG 101"]

    def test_profile_and_courses_recreate_an_unknown_session(self, client):
        session_id = str(uuid.uuid4())

        assert client.post(f"/api/session/{session_id}/profile", json=PROFILE).status_code == 200
        bulk = client.post(f"/api/session/{session_id}/courses/bulk", json=TRANSCRIPT["courses"])
        assert bulk.json() == {"saved": 2, "total": 2}
        assert client.get(f"/api/session/{session_id}").json()["profile"]["school"] == "BMCC"

    def test_advisement_carries_its_own_state_to_any_instance(
        self, client, csc_program, ai_providers
    ):
        ai_providers.primary.queue(TRANSCRIPT, PLAN)
        parsed = client.post(
            f"/api/session/{uuid.uuid4()}/transcript",
            files={"file": ("t.png", BytesIO(b"fake image"), "image/png")},
        ).json()

        # A different instance, which has never seen this session.
        resp = client.post(
            f"/api/session/{uuid.uuid4()}/advisement",
            json={"message": "What next?", "profile": PROFILE, "courses": parsed["courses"]},
        )

        assert resp.status_code == 200
        assert resp.json()["recommended_courses"][0]["course_code"] == "MAT 206"
        prompt = ai_providers.primary.calls[1]["prompt"]
        assert "MAT 157" in prompt and "ENG 101" in prompt
        assert "robotics engineer" in prompt

    def test_state_sent_with_advisement_replaces_stored_state(
        self, client, csc_program, ai_providers
    ):
        ai_providers.primary.queue(PLAN)
        session_id = client.post("/api/session").json()["session_id"]
        client.post(
            f"/api/session/{session_id}/courses",
            json={"course_code": "CSC 999", "status": "completed", "credits": 3},
        )

        resp = client.post(
            f"/api/session/{session_id}/advisement",
            json={"message": "?", "profile": PROFILE, "courses": TRANSCRIPT["courses"]},
        )

        assert resp.status_code == 200
        stored = client.get(f"/api/session/{session_id}").json()["courses"]
        assert sorted(c["course_code"] for c in stored) == ["ENG 101", "MAT 157"]

    def test_malformed_session_ids_are_still_rejected(self, client):
        response = client.post(
            "/api/session/not-a-session/transcript",
            files={"file": ("t.png", BytesIO(b"fake image"), "image/png")},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found"
