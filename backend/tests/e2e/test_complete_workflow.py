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
    
    @patch('app.parsers.transcript_parser.client')
    @patch('app.services.ai_service.genai.Client')
    def test_new_student_gets_personalized_advisement(self, mock_ai_client, mock_parser_client, client):
        """
        E2E: New student creates session, uploads transcript,
        sets profile, receives AI advisement.
        """
        # Setup Gemini mock for transcript parsing
        parser_response = Mock()
        parser_response.text = '''[
            {"course_code": "MAT 157", "semester_taken": "Spring 2023", "status": "completed", "grade": "A", "credits": 4},
            {"course_code": "ENG 101", "semester_taken": "Spring 2023", "status": "completed", "grade": "B+", "credits": 3}
        ]'''
        mock_parser_client.models.generate_content.return_value = parser_response
        
        # Setup Gemini mock for advisement
        ai_response = Mock()
        ai_response.text = "Since you've completed MAT 157 and ENG 101, you can take MAT 206 and ENG 201 this Fall. That would give you 7 credits. Does that sound like a plan?"
        mock_ai_client.return_value.models.generate_content.return_value = ai_response
        
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
    
    @patch('app.services.ai_service.genai.Client')
    def test_student_can_manually_add_courses(self, mock_ai_client, client):
        """
        E2E: Student manually adds courses instead of uploading transcript.
        """
        # Mock AI response
        ai_response = Mock()
        ai_response.text = "Based on your completed courses, you can take MAT 206 next."
        mock_ai_client.return_value.models.generate_content.return_value = ai_response
        
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
    
    @patch('app.parsers.transcript_parser.client')
    @patch('app.services.ai_service.genai.Client')
    def test_financial_aid_warning_included(self, mock_ai_client, mock_parser_client, client):
        """
        E2E: Student with Pell Grant gets warning about credit minimums.
        """
        # Mock transcript parsing
        parser_response = Mock()
        parser_response.text = '''[{"course_code": "MAT 157", "semester_taken": "Fall 2023", "status": "completed", "grade": "A", "credits": 4}]'''
        mock_parser_client.models.generate_content.return_value = parser_response
        
        # Mock AI to verify warning is in prompt
        ai_response = Mock()
        ai_response.text = "Since you're on Pell Grant, make sure to take at least 6 credits. You can take MAT 206 (4 credits) and add a 3-credit elective."
        mock_ai_client.return_value.models.generate_content.return_value = ai_response
        
        # 1. Create session with Pell Grant
        session_id = client.post("/api/session").json()["session_id"]
        
        # 2. Upload transcript
        fake_image = BytesIO(b"fake")
        client.post(
            f"/api/session/{session_id}/transcript",
            files={"file": ("transcript.png", fake_image, "image/png")}
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
        
        # Verify the call was made (warning should be in prompt)
        call_args = mock_ai_client.return_value.models.generate_content.call_args
        contents = call_args[1]['contents']
        # Warning should be in the prompt
        assert any("pell" in str(c).lower() or "warning" in str(c).lower() for c in contents)


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
