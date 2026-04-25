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
    @patch('app.infrastructure.ai.client.genai.Client')
    async def test_prompt_includes_all_student_data(self, mock_client_class, mock_profile):
        """Verify prompt template is populated correctly with all student data."""
        # Arrange
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Test advisement response"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None
        
        service = AIService()
        mock_db = MagicMock()
        
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
        
        # Assert - Verify Gemini was called
        assert mock_client.models.generate_content.called
        call_args = mock_client.models.generate_content.call_args
        
        # Check that contents were passed
        contents = call_args[1]['contents']
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
    @patch('app.infrastructure.ai.client.genai.Client')
    async def test_prompt_handles_empty_courses(self, mock_client_class, mock_profile):
        """Should handle empty course lists gracefully."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "No courses completed yet"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None
        
        service = AIService()
        mock_db = MagicMock()
        
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
    @patch('app.infrastructure.ai.client.genai.Client')
    async def test_handles_gemini_api_error(self, mock_client_class, mock_profile):
        """Should gracefully handle API errors."""
        # Arrange
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client
        
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None
        
        service = AIService()
        mock_db = MagicMock()
        
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
        assert "API Error" in result
    
    @pytest.mark.asyncio
    @patch('app.infrastructure.ai.client.genai.Client')
    async def test_default_message_when_none_provided(self, mock_client_class, mock_profile):
        """Should use default message when student_message is None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Default response"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None
        
        service = AIService()
        mock_db = MagicMock()
        
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
        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]['contents']
        assert "What should I take next?" in contents[1]
    
    @pytest.mark.asyncio
    @patch('app.infrastructure.ai.client.genai.Client')
    async def test_multiple_available_courses_formatted(self, mock_client_class, mock_profile):
        """Should format multiple available courses correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Multiple courses response"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None
        
        service = AIService()
        mock_db = MagicMock()
        
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
        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]['contents']
        user_prompt = contents[1]
        assert "MAT 206: Precalculus" in user_prompt
        assert "ENG 201: Advanced Composition" in user_prompt
        assert "CSC 201: Computer Science I" in user_prompt


@pytest.mark.unit
class TestAIServiceInitialization:
    """Test service setup and configuration."""
    
    @patch('app.infrastructure.ai.client.genai.Client')
    @patch('app.infrastructure.ai.client.settings')
    def test_uses_configured_api_key(self, mock_settings, mock_client_class):
        """Should initialize Gemini with configured API key."""
        mock_settings.GEMINI_API_KEY = "test-api-key"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
        
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None
        
        service = AIService()
        
        mock_client_class.assert_called_once_with(api_key="test-api-key")
    
    @pytest.mark.asyncio
    @patch('app.infrastructure.ai.client.genai.Client')
    @patch('app.infrastructure.ai.client.settings')
    async def test_uses_configured_model(self, mock_settings, mock_client_class):
        """Should use configured model for requests."""
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Response"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Reset singleton to force re-initialization
        from app.infrastructure.ai.client import AIClient
        AIClient._instance = None
        
        service = AIService()
        mock_db = MagicMock()
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
        
        # Verify correct model was used
        call_args = mock_client.models.generate_content.call_args
        assert call_args[1]['model'] == "gemini-2.5-flash"
