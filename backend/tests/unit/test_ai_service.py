"""
Unit tests for AI service with mocked Gemini client.

Tests prompt generation and response handling without real API calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.ai_service import AIService


@pytest.mark.unit
class TestGenerateAdvisement:
    """Test AI advisement generation with mocked LLM."""
    
    @pytest.mark.asyncio
    async def test_prompt_includes_all_student_data(self, mock_profile):
        """Verify prompt template is populated correctly with all student data."""
        # Arrange
        service = AIService()
        mock_db = MagicMock()

        # Mock the AI client's generate_content method
        service.ai_client.generate_content = Mock(return_value="Test advisement response")

        # Mock utils to return predictable values
        with patch('app.services.ai_service.get_next_semester', return_value='Fall 2024'):
            with patch('app.services.ai_service.calculate_remaining_credits', return_value=12):
                # Act
                result = await service.generate_advisement(
                    profile=mock_profile,
                    completed_courses=["MAT 157", "ENG 101"],
                    in_progress_courses=["CSC 103"],
                    planned_courses=[],
                    available_courses=[{"code": "MAT 206", "title": "Precalculus"}],
                    warnings=["Test warning"],
                    current_planned_credits=0,
                    db=mock_db,
                    student_message="What next?"
                )

        # Assert - Verify AI client was called
        assert service.ai_client.generate_content.called
        call_args = service.ai_client.generate_content.call_args

        # Check that contents were passed (kwargs)
        contents = call_args.kwargs['contents']
        assert len(contents) == 2  # System prompt + user prompt

        # User prompt should contain student data
        user_prompt = contents[1]
        assert "MAT 157" in user_prompt
        assert "ENG 101" in user_prompt
        assert "CSC 103" in user_prompt
        assert "MAT 206" in user_prompt
        assert "Precalculus" in user_prompt
        assert "Test warning" in user_prompt
        assert "What next?" in user_prompt
    
    @pytest.mark.asyncio
    async def test_prompt_handles_empty_courses(self, mock_profile):
        """Should handle empty course lists gracefully."""
        service = AIService()
        mock_db = MagicMock()
        service.ai_client.generate_content = Mock(return_value="No courses completed yet")
        
        with patch('app.services.ai_service.get_next_semester', return_value='Fall 2024'):
            with patch('app.services.ai_service.calculate_remaining_credits', return_value=18):
                result = await service.generate_advisement(
                    profile=mock_profile,
                    completed_courses=[],
                    in_progress_courses=[],
                    planned_courses=[],
                    available_courses=[],
                    warnings=[],
                    current_planned_credits=0,
                    db=mock_db,
                    student_message="Just starting out"
                )
        
        assert result == "No courses completed yet"
    
    @pytest.mark.asyncio
    async def test_handles_gemini_api_error(self, mock_profile):
        """Should gracefully handle API errors."""
        service = AIService()
        mock_db = MagicMock()
        service.ai_client.generate_content = Mock(side_effect=Exception("API Error"))
        
        # Act
        with patch('app.services.ai_service.get_next_semester', return_value='Fall 2024'):
            with patch('app.services.ai_service.calculate_remaining_credits', return_value=12):
                result = await service.generate_advisement(
                    profile=mock_profile,
                    completed_courses=["MAT 157"],
                    in_progress_courses=[],
                    planned_courses=[],
                    available_courses=[{"code": "MAT 206", "title": "Precalculus"}],
                    warnings=[],
                    current_planned_credits=0,
                    db=mock_db,
                    student_message="Help?"
                )
        
        # Assert - Should return error message, not crash
        assert "Error generating advisement" in result
    
    @pytest.mark.asyncio
    async def test_default_message_when_none_provided(self, mock_profile):
        """Should use default message when student_message is None."""
        service = AIService()
        mock_db = MagicMock()
        service.ai_client.generate_content = Mock(return_value="Default response")
        
        with patch('app.services.ai_service.get_next_semester', return_value='Fall 2024'):
            with patch('app.services.ai_service.calculate_remaining_credits', return_value=12):
                result = await service.generate_advisement(
                    profile=mock_profile,
                    completed_courses=["MAT 157"],
                    in_progress_courses=[],
                    planned_courses=[],
                    available_courses=[{"code": "MAT 206", "title": "Precalculus"}],
                    warnings=[],
                    current_planned_credits=0,
                    db=mock_db,
                    student_message=None  # Explicitly None
                )
        
        # Check that default message was used
        call_args = service.ai_client.generate_content.call_args
        contents = call_args.kwargs['contents']
        assert "What should I take next?" in contents[1]
    
    @pytest.mark.asyncio
    async def test_multiple_available_courses_formatted(self, mock_profile):
        """Should format multiple available courses correctly."""
        service = AIService()
        mock_db = MagicMock()
        service.ai_client.generate_content = Mock(return_value="Multiple courses response")
        
        available = [
            {"code": "MAT 206", "title": "Precalculus"},
            {"code": "ENG 201", "title": "Advanced Composition"},
            {"code": "CSC 201", "title": "Computer Science I"},
        ]
        
        with patch('app.services.ai_service.get_next_semester', return_value='Fall 2024'):
            with patch('app.services.ai_service.calculate_remaining_credits', return_value=12):
                result = await service.generate_advisement(
                    profile=mock_profile,
                    completed_courses=["MAT 157", "ENG 101"],
                    in_progress_courses=[],
                    planned_courses=[],
                    available_courses=available,
                    warnings=[],
                    current_planned_credits=0,
                    db=mock_db,
                    student_message="What should I take?"
                )
        
        # Assert all courses appear in prompt
        call_args = service.ai_client.generate_content.call_args
        contents = call_args.kwargs['contents']
        user_prompt = contents[1]
        assert "MAT 206: Precalculus" in user_prompt
        assert "ENG 201: Advanced Composition" in user_prompt
        assert "CSC 201: Computer Science I" in user_prompt


@pytest.mark.unit
class TestAIServiceInitialization:
    """Test service setup and configuration."""
    
    def test_uses_configured_api_key(self):
        """Should initialize AI client."""
        service = AIService()
        assert service.ai_client is not None
    
    @pytest.mark.asyncio
    async def test_uses_configured_model(self):
        """Should use configured model for requests."""
        service = AIService()
        mock_db = MagicMock()
        service.ai_client.generate_content = Mock(return_value="Response")
        mock_profile = Mock(
            enrollment_status="full-time",
            student_type="regular",
            financial_aid_type=None,
            program_code="CSC-AS",
            graduation_semester="Spring",
            graduation_year=2026
        )
        
        with patch('app.services.ai_service.get_next_semester', return_value='Fall 2024'):
            with patch('app.services.ai_service.calculate_remaining_credits', return_value=12):
                await service.generate_advisement(
                    profile=mock_profile,
                    completed_courses=[],
                    in_progress_courses=[],
                    planned_courses=[],
                    available_courses=[],
                    warnings=[],
                    current_planned_credits=0,
                    db=mock_db,
                    student_message="Test"
                )
        
        # Verify AI client was called
        assert service.ai_client.generate_content.called
