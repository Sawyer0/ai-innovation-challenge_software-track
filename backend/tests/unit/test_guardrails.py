"""
Unit tests for the deterministic guardrails the README promises: Pell proration,
F-1 visa rules and TAP elective annotation.
"""

import pytest

from app import models
from app.academics.compliance import (
    calculate_pell_proration,
    check_tap_elective_compliance,
    check_visa_compliance,
)
from app.schemas import RecommendedCourse


@pytest.mark.unit
class TestPellProration:
    @pytest.mark.parametrize(
        "credits,display,tier",
        [
            (15, "100%", "full-time"),
            (12, "100%", "full-time"),
            (9, "75%", "three-quarter-time"),
            (6, "50%", "half-time"),
            (3, "25%", "less-than-half-time"),
            (0, "0%", "less-than-half-time"),
        ],
    )
    def test_tiers(self, credits: float, display: str, tier: str) -> None:
        result = calculate_pell_proration("pell", credits)

        assert result is not None
        assert result["percentage_display"] == display
        assert result["enrollment_tier"] == tier

    def test_below_full_time_suggests_next_tier(self) -> None:
        result = calculate_pell_proration("pell", 9)

        assert result is not None
        assert "12+ credits" in result["note"]

    def test_applies_to_students_with_both_awards(self) -> None:
        assert calculate_pell_proration("both", 12) is not None

    @pytest.mark.parametrize("aid", [None, "tap", "loans"])
    def test_skipped_without_pell(self, aid: str | None) -> None:
        assert calculate_pell_proration(aid, 12) is None


@pytest.mark.unit
class TestVisaCompliance:
    def test_non_international_students_are_not_checked(self, db) -> None:
        assert check_visa_compliance("continuing", 3, [], db) == (True, None)

    def test_no_planned_courses_yet_is_allowed(self, db) -> None:
        assert check_visa_compliance("international", 0, [], db) == (True, None)

    def test_under_twelve_credits_is_blocked(self, db) -> None:
        ok, message = check_visa_compliance("International", 9, ["ENG 101"], db)

        assert ok is False
        assert message is not None and "12 credits" in message

    def test_one_online_course_is_allowed(self, db) -> None:
        db.add(models.Course(code="CSC 101", title="x", credits=3, instruction_mode="Online"))
        db.commit()

        assert check_visa_compliance("international", 12, ["CSC 101"], db) == (True, None)

    def test_two_online_or_hybrid_courses_are_blocked(self, db) -> None:
        db.add_all(
            [
                models.Course(code="CSC 101", title="x", credits=3, instruction_mode="Online"),
                models.Course(code="CSC 102", title="y", credits=3, instruction_mode="Hybrid"),
            ]
        )
        db.commit()

        ok, message = check_visa_compliance("international", 12, ["CSC 101", "CSC 102"], db)

        assert ok is False
        assert message is not None and "2 online/hybrid" in message


def _course(code: str) -> RecommendedCourse:
    return RecommendedCourse(
        course_code=code,
        course_title=code,
        credits=3,
        requirement_satisfied="",
        compliance_status="compliant",
        compliance_note=None,
        career_rationale="",
        why_now="",
    )


@pytest.mark.unit
class TestTapElectiveCompliance:
    @pytest.fixture
    def program(self, db) -> None:
        program = models.Program(program_code="CSC-AS", name="Computer Science")
        db.add(program)
        db.commit()
        db.add_all(
            [
                models.ProgramRequirement(
                    program_id=program.id, course_code="MAT 206", is_required=True
                ),
                models.ProgramRequirement(
                    program_id=program.id, course_code="CSC 211", is_required=False
                ),
            ]
        )
        db.commit()

    def test_flags_only_courses_outside_the_program(self, db, program) -> None:
        courses = [_course("MAT 206"), _course("CSC 211"), _course("ART 100")]

        check_tap_elective_compliance("tap", "CSC-AS", courses, db)

        assert [c.compliance_status for c in courses] == ["compliant", "compliant", "warning"]
        assert courses[2].compliance_note is not None
        assert "TAP-allowable" in courses[2].compliance_note

    def test_non_tap_students_are_untouched(self, db, program) -> None:
        courses = [_course("ART 100")]

        check_tap_elective_compliance("pell", "CSC-AS", courses, db)

        assert courses[0].compliance_status == "compliant"
