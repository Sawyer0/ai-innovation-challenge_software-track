"""
Integration tests for API endpoints with test database.

Tests use FastAPI TestClient with real (test) database.
External APIs are mocked.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


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
            json={
                "school": "BMCC",
                "program_code": "CSC-AS",
                "enrollment_status": "full-time"
            }
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
                "credits": 4
            }
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
            f"/api/session/{session_id}/profile",
            json={"school": "BMCC", "program_code": "CSC-AS"}
        )
        
        assert response.status_code == 200
        assert response.json()["program_code"] == "CSC-AS"
    
    def test_set_profile_updates_existing(self, client):
        """POST /api/session/{id}/profile should update existing profile."""
        session_id = client.post("/api/session").json()["session_id"]
        
        # Create initial profile
        client.post(
            f"/api/session/{session_id}/profile",
            json={"program_code": "CSC-AS"}
        )
        
        # Update it
        response = client.post(
            f"/api/session/{session_id}/profile",
            json={"program_code": "ACC-AAS", "enrollment_status": "half-time"}
        )
        
        assert response.status_code == 200
        assert response.json()["program_code"] == "ACC-AAS"
        assert response.json()["enrollment_status"] == "half-time"


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
        program = models.Program(
            program_code="CSC-AS",
            name="Computer Science",
            degree="A.S."
        )
        db.add(program)
        db.commit()
        db.refresh(program)
        
        # Add requirements
        req = models.ProgramRequirement(
            program_id=program.id,
            course_code="MAT 206",
            semester_year="Year 1",
            semester_term="Fall",
            is_required=True
        )
        db.add(req)
        db.commit()
        
        response = client.get("/api/programs/CSC-AS")
        
        assert response.status_code == 200
        data = response.json()
        assert data["program_code"] == "CSC-AS"


@pytest.mark.integration
class TestAdvisementEndpoints:
    """Test AI advisement flow with mocked Gemini."""
    
    @patch('app.infrastructure.ai.client.genai.Client')
    def test_get_eligible_courses(self, mock_client_class, client, db):
        """GET /api/advisement/eligible returns courses student can take."""
        from app import models
        
        # Seed courses and prerequisites
        mat157 = models.Course(code="MAT 157", title="College Algebra", credits=4)
        mat206 = models.Course(code="MAT 206", title="Precalculus", credits=4)
        db.add_all([mat157, mat206])
        db.commit()
        
        # Seed prerequisite: MAT 206 requires MAT 157
        prereq = models.CoursePrerequisite(
            course_id=mat206.id,
            prerequisite_course_code="MAT 157",
            logic_group=1
        )
        db.add(prereq)
        
        # Seed program
        program = models.Program(program_code="CSC-AS", name="Computer Science", degree="A.S.")
        db.add(program)
        db.commit()
        
        # Add requirement
        req = models.ProgramRequirement(
            program_id=program.id,
            course_code="MAT 206",
            is_required=True
        )
        db.add(req)
        db.commit()
        
        # Create session with completed MAT 157
        session_resp = client.post("/api/session")
        session_id = session_resp.json()["session_id"]
        
        client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "full-time"
        })
        
        client.post(f"/api/session/{session_id}/courses", json={
            "course_code": "MAT 157",
            "status": "completed",
            "credits": 4
        })
        
        # Get eligible courses
        response = client.get(f"/api/advisement/eligible?session_id={session_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "eligible_courses" in data
        # MAT 206 should be eligible (prereq satisfied)
        assert "MAT 206" in data["eligible_courses"]
    
    @patch('app.infrastructure.ai.client.genai.Client')
    def test_advisement_endpoint(self, mock_client_class, client, db):
        """POST /api/advisement returns AI-generated response."""
        # Reset singleton and mock Gemini response
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None

        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Since you've completed MAT 157, you can take MAT 206 this Fall."
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Setup session
        session_id = client.post("/api/session").json()["session_id"]
        client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "full-time"
        })
        client.post(f"/api/session/{session_id}/courses", json={
            "course_code": "MAT 157",
            "status": "completed",
            "credits": 4
        })
        
        # Request advisement
        response = client.post(f"/api/advisement?session_id={session_id}", json={
            "message": "What should I take next?"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_advisement_requires_profile(self, client):
        """POST /api/advisement should 400 if no profile set."""
        session_id = client.post("/api/session").json()["session_id"]
        
        response = client.post(f"/api/advisement?session_id={session_id}", json={
            "message": "Help?"
        })
        
        assert response.status_code == 400
        assert "profile not set" in response.json()["detail"].lower()


@pytest.mark.integration
class TestTranscriptEndpoints:
    """Test transcript upload flow."""
    
    @patch('app.services.parser_service.detect_and_parse')
    def test_upload_image_parsed_and_saved(self, mock_detect_and_parse, client, db):
        """Upload PDF -> Parser parses -> courses saved to DB."""
        from io import BytesIO
        import os

        # Mock the parser to return structured data
        mock_detect_and_parse.return_value = {
            "source": "transcript",
            "confidence": 0.9,
            "student": {},
            "courses": {
                "completed": [{"course_code": "MAT 206", "semester_taken": "Fall 2023", "status": "completed", "grade": "B+", "credits": 4}],
                "in_progress": [],
                "still_needed": [],
                "fall_through": []
            },
            "all_courses": [{"course_code": "MAT 206", "semester_taken": "Fall 2023", "status": "completed", "grade": "B+", "credits": 4}],
            "requirements": [],
            "validated": [{"course_code": "MAT 206", "semester_taken": "Fall 2023", "status": "completed", "grade": "B+", "credits": 4}],
            "flagged": [],
            "invalid": [],
            "requires_confirmation": False
        }

        # Create session
        session_id = client.post("/api/session").json()["session_id"]

        # Upload actual PDF file
        pdf_path = os.path.join(os.path.dirname(__file__), "../../assets/degree-works-ds.pdf")
        with open(pdf_path, "rb") as pdf_file:
            response = client.post(
                f"/api/session/{session_id}/transcript",
                files={"file": ("degree-works-ds.pdf", pdf_file, "application/pdf")}
            )

        assert response.status_code == 200
        data = response.json()
        assert "Successfully parsed" in data["message"]
        assert len(data["all_courses"]) == 1
        assert data["all_courses"][0]["course_code"] == "MAT 206"

        # Verify saved to DB
        session_data = client.get(f"/api/session/{session_id}").json()
        assert len(session_data["courses"]) == 1
        assert session_data["courses"][0]["course_code"] == "MAT 206"
        assert session_data["courses"][0]["source"] == "transcript"
    
    def test_upload_requires_valid_session(self, client):
        """Should 404 if session doesn't exist."""
        from io import BytesIO
        
        fake_image = BytesIO(b"fake")
        response = client.post(
            "/api/session/invalid-session/transcript",
            files={"file": ("test.png", fake_image, "image/png")}
        )
        
        assert response.status_code == 404
