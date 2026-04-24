"""
Unit tests for prerequisite checking logic.

Fast, isolated tests - no database required.
Uses mocking for database dependency.
"""

import pytest
from unittest.mock import Mock, MagicMock
from app.services.prerequisite_service import PrerequisiteService


@pytest.fixture
def mock_repos():
    """Provide mock repositories for PrerequisiteService."""
    mock_program_repo = Mock()
    mock_course_repo = Mock()
    return mock_program_repo, mock_course_repo


@pytest.mark.unit
class TestCheckPrerequisites:
    """Test prerequisite satisfaction logic."""
    
    def test_no_prerequisites_required(self, mock_repos):
        """Course with no prereqs should be available to anyone."""
        # Arrange
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        # Mock get_prerequisites to return empty list
        service.get_prerequisites = Mock(return_value=[])
        
        # Act
        result = service.check_prerequisites("ENG 101", [])
        
        # Assert
        assert result is True
    
    def test_single_prerequisite_satisfied(self, mock_repos):
        """Should pass when required course completed."""
        # Arrange
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        # Create mock prerequisite
        mock_prereq = Mock()
        mock_prereq.prerequisite_course_code = "MAT 157"
        mock_prereq.logic_group = 1
        mock_prereq.is_corequisite = False
        
        service.get_prerequisites = Mock(return_value=[mock_prereq])
        
        # Act
        result = service.check_prerequisites("MAT 206", ["MAT 157"])
        
        # Assert
        assert result is True
    
    def test_single_prerequisite_missing(self, mock_repos):
        """Should fail when required course not completed."""
        # Arrange
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        mock_prereq = Mock()
        mock_prereq.prerequisite_course_code = "MAT 157"
        mock_prereq.logic_group = 1
        
        service.get_prerequisites = Mock(return_value=[mock_prereq])
        
        # Act
        result = service.check_prerequisites("MAT 206", [])
        
        # Assert
        assert result is False
    
    def test_or_condition_one_satisfied(self, mock_repos):
        """Should pass if at least one option in OR group satisfied."""
        # Arrange - MAT 206 requires MAT 056 OR MAT 150
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        prereq1 = Mock()
        prereq1.prerequisite_course_code = "MAT 056"
        prereq1.logic_group = 1
        
        prereq2 = Mock()
        prereq2.prerequisite_course_code = "MAT 150"
        prereq2.logic_group = 1
        
        service.get_prerequisites = Mock(return_value=[prereq1, prereq2])
        
        # Act - Has MAT 056 but not MAT 150
        result = service.check_prerequisites("MAT 206", ["MAT 056"])
        
        # Assert
        assert result is True
    
    def test_or_condition_none_satisfied(self, mock_repos):
        """Should fail if no option in OR group satisfied."""
        # Arrange
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        prereq1 = Mock()
        prereq1.prerequisite_course_code = "MAT 056"
        prereq1.logic_group = 1
        
        prereq2 = Mock()
        prereq2.prerequisite_course_code = "MAT 150"
        prereq2.logic_group = 1
        
        service.get_prerequisites = Mock(return_value=[prereq1, prereq2])
        
        # Act - Has neither prerequisite
        result = service.check_prerequisites("MAT 206", ["ENG 101"])
        
        # Assert
        assert result is False
    
    def test_multiple_and_conditions_all_satisfied(self, mock_repos):
        """Should pass when all AND groups satisfied."""
        # Arrange - Course requires (MAT 157 OR MAT 150) AND (ENG 101)
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        prereq1 = Mock()
        prereq1.prerequisite_course_code = "MAT 157"
        prereq1.logic_group = 1  # OR group 1
        
        prereq2 = Mock()
        prereq2.prerequisite_course_code = "MAT 150"
        prereq2.logic_group = 1  # OR group 1
        
        prereq3 = Mock()
        prereq3.prerequisite_course_code = "ENG 101"
        prereq3.logic_group = 2  # AND group 2 (different from 1)
        
        service.get_prerequisites = Mock(return_value=[prereq1, prereq2, prereq3])
        
        # Act
        result = service.check_prerequisites("CSC 201", ["MAT 157", "ENG 101"])
        
        # Assert
        assert result is True
    
    def test_multiple_and_conditions_one_group_missing(self, mock_repos):
        """Should fail when one AND group not satisfied."""
        # Arrange
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        prereq1 = Mock()
        prereq1.prerequisite_course_code = "MAT 157"
        prereq1.logic_group = 1
        
        prereq2 = Mock()
        prereq2.prerequisite_course_code = "ENG 101"
        prereq2.logic_group = 2
        
        service.get_prerequisites = Mock(return_value=[prereq1, prereq2])
        
        # Act - Has math prereq but not English
        result = service.check_prerequisites("CSC 201", ["MAT 157"])
        
        # Assert
        assert result is False


@pytest.mark.unit
class TestRemainingRequirements:
    """Test degree requirement tracking."""
    
    def test_returns_uncompleted_courses(self, mock_repos):
        """Should return only courses not yet taken."""
        # Arrange
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        # Mock program with requirements
        mock_program = Mock()
        mock_req1 = Mock()
        mock_req1.course_code = "MAT 206"
        mock_req2 = Mock()
        mock_req2.course_code = "ENG 201"
        mock_req3 = Mock()
        mock_req3.course_code = "CSC 103"
        mock_program.requirements = [mock_req1, mock_req2, mock_req3]
        
        mock_program_repo.get_by_code.return_value = mock_program
        
        completed = ["MAT 157", "ENG 101", "CSC 103"]
        
        # Act
        result = service.get_remaining_requirements("CSC-AS", completed)
        
        # Assert
        assert "MAT 206" in result
        assert "ENG 201" in result
        assert "CSC 103" not in result  # Already completed
    
    def test_handles_program_not_found(self, mock_repos):
        """Should return empty list for invalid program."""
        # Arrange
        mock_program_repo, mock_course_repo = mock_repos
        service = PrerequisiteService(program_repo=mock_program_repo, course_repo=mock_course_repo)
        
        mock_program_repo.get_by_code.return_value = None
        
        # Act
        result = service.get_remaining_requirements("INVALID", [])
        
        # Assert
        assert result == []
