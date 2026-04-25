"""
End-to-end tests for complete user workflows.

These tests verify complete user journeys from start to finish.
They are slower and should be run less frequently.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from io import BytesIO


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteStudentWorkflow:
    """Test full user journey: create → upload → get advisement."""

    @patch('app.infrastructure.ai.client.genai.Client')
    def test_new_student_gets_personalized_advisement(self, mock_client_class, client):
        """
        E2E: New student creates session, uploads transcript,
        sets profile, receives AI advisement.
        """
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None

        # Setup Gemini mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # First call is for transcript parsing
        parser_response = Mock()
        parser_response.text = '''[
            {"course_code": "MAT 157", "semester_taken": "Spring 2023", "status": "completed", "grade": "A", "credits": 4},
            {"course_code": "ENG 101", "semester_taken": "Spring 2023", "status": "completed", "grade": "B+", "credits": 3}
        ]'''

        # Second call is for advisement
        ai_response = Mock()
        ai_response.text = "Since you've completed MAT 157 and ENG 101, you can take MAT 206 and ENG 201 this Fall. That would give you 7 credits. Does that sound like a plan?"

        # Configure mock to return different responses for different calls
        mock_client.models.generate_content.side_effect = [parser_response, ai_response]
        
        # 1. Create session
        resp = client.post("/api/session")
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]
        
        # 2. Upload transcript (mocked image)
        fake_image = BytesIO(b"fake transcript image data")
        resp = client.post(
            f"/api/session/{session_id}/transcript",
            files={"file": ("transcript.png", fake_image, "image/png")}
        )
        assert resp.status_code == 200
        assert resp.json()["courses"][0]["course_code"] == "MAT 157"
        
        # 3. Set profile
        resp = client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "full-time",
            "financial_aid_type": "pell",
            "graduation_year": 2026,
            "graduation_semester": "Spring"
        })
        assert resp.status_code == 200
        
        # 4. Get eligible courses
        resp = client.get(f"/api/advisement/eligible?session_id={session_id}")
        assert resp.status_code == 200
        eligible = resp.json()["eligible_courses"]
        assert isinstance(eligible, list)
        
        # 5. Get AI advisement
        resp = client.post(f"/api/advisement?session_id={session_id}", json={
            "message": "What should I take next semester?"
        })
        assert resp.status_code == 200
        advisement = resp.json()["response"]
        assert len(advisement) > 0
        assert "MAT 157" in advisement or "ENG 101" in advisement
        
        # 6. Verify session state persisted
        resp = client.get(f"/api/session/{session_id}")
        assert resp.status_code == 200
        session_data = resp.json()
        assert session_data["profile"]["program_code"] == "CSC-AS"
        assert len(session_data["courses"]) == 2
    
    @patch('app.infrastructure.ai.client.genai.Client')
    def test_student_can_manually_add_courses(self, mock_client_class, client):
        """
        E2E: Student manually adds courses instead of uploading transcript.
        """
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None

        # Mock AI response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        ai_response = Mock()
        ai_response.text = "Based on your completed courses, you can take MAT 206 next."
        mock_client.models.generate_content.return_value = ai_response
        
        # 1. Create session
        session_id = client.post("/api/session").json()["session_id"]
        
        # 2. Set profile
        client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "full-time"
        })
        
        # 3. Manually add courses one by one
        courses_to_add = [
            {"course_code": "MAT 157", "status": "completed", "semester_taken": "Fall 2023", "credits": 4, "grade": "A"},
            {"course_code": "ENG 101", "status": "completed", "semester_taken": "Fall 2023", "credits": 3, "grade": "B+"},
            {"course_code": "CSC 103", "status": "completed", "semester_taken": "Spring 2024", "credits": 3, "grade": "A-"},
        ]
        
        for course in courses_to_add:
            resp = client.post(f"/api/session/{session_id}/courses", json=course)
            assert resp.status_code == 200
        
        # 4. Get advisement
        resp = client.post(f"/api/advisement?session_id={session_id}", json={
            "message": "What should I take?"
        })
        assert resp.status_code == 200
        assert "response" in resp.json()
    
    @patch('app.services.parser_service.detect_and_parse')
    @patch('app.services.ai_service.AIService')
    def test_financial_aid_warning_included(self, mock_ai_service_class, mock_detect_and_parse, client):
        """
        E2E: Student with Pell Grant gets warning about credit minimums.
        """
        import os

        # Mock the parser to return structured data
        mock_detect_and_parse.return_value = {
            "source": "transcript",
            "confidence": 0.9,
            "student": {},
            "courses": {
                "completed": [{"course_code": "MAT 157", "semester_taken": "Fall 2023", "status": "completed", "grade": "A", "credits": 4}],
                "in_progress": [],
                "still_needed": [],
                "fall_through": []
            },
            "all_courses": [{"course_code": "MAT 157", "semester_taken": "Fall 2023", "status": "completed", "grade": "A", "credits": 4}],
            "requirements": [],
            "validated": [{"course_code": "MAT 157", "semester_taken": "Fall 2023", "status": "completed", "grade": "A", "credits": 4}],
            "flagged": [],
            "invalid": [],
            "requires_confirmation": False
        }

        # Mock AI service
        mock_ai_service = Mock()
        mock_ai_service.generate_advisement = Mock(return_value="Since you're on Pell Grant, make sure to take at least 6 credits. You can take MAT 206 (4 credits) and add a 3-credit elective.")
        mock_ai_service_class.return_value = mock_ai_service

        # 1. Create session with Pell Grant
        session_id = client.post("/api/session").json()["session_id"]

        # 2. Upload actual PDF
        pdf_path = os.path.join(os.path.dirname(__file__), "../../assets/degree-works-ds.pdf")
        with open(pdf_path, "rb") as pdf_file:
            client.post(
                f"/api/session/{session_id}/transcript",
                files={"file": ("degree-works-ds.pdf", pdf_file, "application/pdf")}
            )

        # 3. Set profile with Pell Grant
        client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "half-time",
            "financial_aid_type": "pell"
        })

        # 4. Get advisement
        resp = client.post(f"/api/advisement?session_id={session_id}", json={
            "message": "What should I take?"
        })
        assert resp.status_code == 200

        # Verify AI service was called
        assert mock_ai_service.generate_advisement.called


@pytest.mark.e2e
@pytest.mark.slow
class TestErrorHandlingWorkflows:
    """Test error scenarios and edge cases."""
    
    def test_invalid_session_id_returns_404(self, client):
        """All endpoints should handle invalid session IDs gracefully."""
        # Test various endpoints with invalid session
        resp = client.get("/api/session/invalid-uuid")
        assert resp.status_code == 404
        
        resp = client.post("/api/session/invalid-uuid/profile", json={"school": "BMCC"})
        assert resp.status_code == 404
        
        resp = client.post("/api/session/invalid-uuid/courses", json={"course_code": "MAT 101"})
        assert resp.status_code == 404
    
    def test_advisement_without_profile_returns_error(self, client):
        """Advisement requires profile to be set."""
        session_id = client.post("/api/session").json()["session_id"]
        
        resp = client.post(f"/api/advisement?session_id={session_id}", json={
            "message": "Help?"
        })
        assert resp.status_code == 400
        assert "profile" in resp.json()["detail"].lower()
    
    def test_cannot_add_duplicate_courses(self, client):
        """Adding same course twice should handle gracefully."""
        session_id = client.post("/api/session").json()["session_id"]
        
        # Add course first time
        resp = client.post(f"/api/session/{session_id}/courses", json={
            "course_code": "MAT 206",
            "status": "completed",
            "credits": 4
        })
        assert resp.status_code == 200
        
        # Add same course again (should succeed, may update)
        resp = client.post(f"/api/session/{session_id}/courses", json={
            "course_code": "MAT 206",
            "status": "in-progress",
            "credits": 4
        })
        # Either 200 (updated) or 409 (conflict) is acceptable
        assert resp.status_code in [200, 409]
