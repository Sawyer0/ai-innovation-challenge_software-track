"""
Unit tests for academic utility functions.

Tests semester calculations and enrollment rules.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from app.utils.academic_utils import (
    get_next_semester,
    get_current_semester,
    calculate_remaining_credits,
    check_financial_aid_compliance,
    parse_semester,
    get_current_academic_year,
)


@pytest.mark.unit
class TestGetNextSemester:
    """Test next semester calculation based on current date."""
    
    @pytest.mark.parametrize("month,expected", [
        (9, "Spring 2025"),   # Fall -> Spring
        (10, "Spring 2025"), # Fall -> Spring
        (11, "Spring 2025"), # Fall -> Spring
        (12, "Spring 2025"), # Fall -> Spring
        (1, "Summer 2024"),   # Early Spring -> Summer
        (2, "Summer 2024"),   # Spring -> Summer
        (3, "Summer 2024"),   # Early Spring -> Summer
        (4, "Fall 2024"),     # Late Spring -> Fall
        (5, "Fall 2024"),     # Late Spring -> Fall
        (6, "Fall 2024"),     # Summer -> Fall
        (7, "Fall 2024"),     # Summer -> Fall
        (8, "Fall 2024"),     # Summer -> Fall
    ])
    def test_next_semester_calculation(self, month, expected, monkeypatch):
        """Parametrized test for various months."""
        # Mock datetime.now()
        mock_now = Mock()
        mock_now.month = month
        mock_now.year = 2024
        
        monkeypatch.setattr('app.utils.academic_utils.datetime', Mock(now=Mock(return_value=mock_now)))
        
        result = get_next_semester()
        assert result == expected


@pytest.mark.unit
class TestGetCurrentSemester:
    """Test current semester identification."""
    
    @pytest.mark.parametrize("month,expected", [
        (9, "Fall 2024"),
        (10, "Fall 2024"),
        (11, "Fall 2024"),
        (12, "Fall 2024"),
        (1, "Spring 2024"),
        (2, "Spring 2024"),
        (3, "Spring 2024"),
        (4, "Spring 2024"),
        (5, "Spring 2024"),
        (6, "Summer 2024"),
        (7, "Summer 2024"),
        (8, "Summer 2024"),
    ])
    def test_current_semester_calculation(self, month, expected, monkeypatch):
        """Current semester should match month."""
        mock_now = Mock()
        mock_now.month = month
        mock_now.year = 2024
        
        monkeypatch.setattr('app.utils.academic_utils.datetime', Mock(now=Mock(return_value=mock_now)))
        
        result = get_current_semester()
        assert result == expected


@pytest.mark.unit
class TestParseSemester:
    """Test semester string parsing."""
    
    def test_parse_fall_2024(self):
        """Should parse 'Fall 2024' correctly."""
        term, year = parse_semester("Fall 2024")
        assert term == "Fall"
        assert year == 2024
    
    def test_parse_spring_2025(self):
        """Should parse 'Spring 2025' correctly."""
        term, year = parse_semester("Spring 2025")
        assert term == "Spring"
        assert year == 2025
    
    def test_parse_summer(self):
        """Should parse 'Summer 2024' correctly."""
        term, year = parse_semester("Summer 2024")
        assert term == "Summer"
        assert year == 2024


@pytest.mark.unit
class TestCalculateRemainingCredits:
    """Test credit capacity calculations."""
    
    @pytest.mark.parametrize("status,planned,expected", [
        ("full-time", 0, 18),      # 18 - 0 = 18
        ("full-time", 12, 6),      # 18 - 12 = 6
        ("full-time", 18, 0),      # 18 - 18 = 0
        ("full-time", 20, 0),      # Cap at 0 (don't go negative)
        ("half-time", 0, 11),       # 11 - 0 = 11
        ("half-time", 6, 5),        # 11 - 6 = 5
        ("half-time", 11, 0),       # 11 - 11 = 0
        ("less-than-half-time", 0, 5),  # 5 - 0 = 5
        ("less-than-half-time", 3, 2),  # 5 - 3 = 2
    ])
    def test_calculations(self, status, planned, expected):
        """Parametrized test for various enrollment scenarios."""
        # Arrange
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        
        # Mock enrollment rule
        mock_rule = Mock()
        mock_rule.max_credits = {
            "full-time": 18,
            "half-time": 11,
            "less-than-half-time": 5
        }.get(status, 18)
        
        mock_first.return_value = mock_rule
        mock_filter.return_value = Mock(first=mock_first)
        mock_query.return_value = Mock(filter=mock_filter)
        mock_db.query.return_value = mock_query.return_value
        
        # Act
        result = calculate_remaining_credits(status, planned, mock_db)
        
        # Assert
        assert result == expected
    
    def test_default_to_full_time_if_status_not_found(self):
        """Should default to full-time rules for unknown status."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = calculate_remaining_credits("unknown-status", 10, mock_db)
        
        # Should use full-time default (18 max)
        assert result == 8


@pytest.mark.unit
class TestCheckFinancialAidCompliance:
    """Test financial aid constraint checking."""
    
    def test_pell_grant_satisfied(self):
        """Pell requires 6+ credits."""
        mock_db = MagicMock()
        
        mock_constraint = Mock()
        mock_constraint.min_credits_required = 6
        mock_constraint.warning_message = "Pell requires 6+ credits"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_constraint
        
        compliant, warning = check_financial_aid_compliance(
            "pell", 9, "half-time", mock_db
        )
        
        assert compliant is True
        assert warning is None
    
    def test_pell_grant_under_minimum(self):
        """Pell warning when under 6 credits."""
        mock_db = MagicMock()
        
        mock_constraint = Mock()
        mock_constraint.min_credits_required = 6
        mock_constraint.warning_message = "Pell Grant requires 6+ credits"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_constraint
        
        compliant, warning = check_financial_aid_compliance(
            "pell", 3, "less-than-half-time", mock_db
        )
        
        assert compliant is False
        assert "Pell" in warning
    
    def test_tap_requires_full_time(self):
        """TAP requires 12+ credits."""
        mock_db = MagicMock()
        
        mock_constraint = Mock()
        mock_constraint.min_credits_required = 12
        mock_constraint.warning_message = "TAP requires 12 credits"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_constraint
        
        compliant, warning = check_financial_aid_compliance(
            "tap", 9, "half-time", mock_db
        )
        
        assert compliant is False
        assert "12" in warning
    
    def test_no_aid_always_compliant(self):
        """No aid type = always compliant."""
        mock_db = MagicMock()
        
        compliant, warning = check_financial_aid_compliance(
            None, 3, "part-time", mock_db
        )
        
        assert compliant is True
        assert warning is None
    
    def test_unknown_aid_type_defaults_compliant(self):
        """Unknown aid type = check passes (no constraint found)."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        compliant, warning = check_financial_aid_compliance(
            "unknown-aid", 3, "part-time", mock_db
        )
        
        assert compliant is True
        assert warning is None


@pytest.mark.unit
class TestGetCurrentAcademicYear:
    """Test academic year calculation."""
    
    def test_fall_semester_same_year(self, monkeypatch):
        """Sept-Dec: Academic year is current year."""
        mock_now = Mock()
        mock_now.month = 9
        mock_now.year = 2024
        
        monkeypatch.setattr('app.utils.academic_utils.datetime', Mock(now=Mock(return_value=mock_now)))
        
        result = get_current_academic_year()
        assert result == 2024
    
    def test_spring_semester_previous_year(self, monkeypatch):
        """Jan-Aug: Academic year is previous year."""
        mock_now = Mock()
        mock_now.month = 3
        mock_now.year = 2024
        
        monkeypatch.setattr('app.utils.academic_utils.datetime', Mock(now=Mock(return_value=mock_now)))
        
        result = get_current_academic_year()
        assert result == 2023
