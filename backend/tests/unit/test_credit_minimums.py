"""Minimum-credit rules for every aid program and F-1, checked against a finished plan."""

import pytest

from app.academics.compliance import check_financial_aid_compliance, check_visa_compliance


@pytest.mark.unit
class TestAidMinimums:
    def test_tap_rejects_eleven_credits_with_specific_message(self, db) -> None:
        ok, message = check_financial_aid_compliance(
            "tap", 11, "full-time", db, allow_empty_plan=False
        )

        assert ok is False
        assert message is not None
        assert "11 credits" in message
        assert "TAP requires at least 12 credits" in message

    def test_tap_accepts_twelve_credits(self, db) -> None:
        assert check_financial_aid_compliance(
            "tap", 12, "full-time", db, allow_empty_plan=False
        ) == (True, None)

    def test_aid_type_is_matched_case_insensitively(self, db) -> None:
        ok, _ = check_financial_aid_compliance("TAP", 11, "full-time", db)

        assert ok is False

    def test_empty_finished_plan_fails(self, db) -> None:
        ok, _ = check_financial_aid_compliance("tap", 0, "full-time", db, allow_empty_plan=False)

        assert ok is False

    def test_empty_plan_before_ai_still_passes(self, db) -> None:
        assert check_financial_aid_compliance("tap", 0, "full-time", db) == (True, None)

    @pytest.mark.parametrize(("credits", "ok"), [(5, False), (6, True)])
    def test_pell_half_time_minimum(self, db, credits: float, ok: bool) -> None:
        result, _ = check_financial_aid_compliance(
            "pell", credits, "half-time", db, allow_empty_plan=False
        )

        assert result is ok

    def test_advisory_constraint_never_blocks(self, db) -> None:
        """Excelsior's 15 credits is a recommendation (block_underload=False)."""
        assert check_financial_aid_compliance(
            "excelsior", 12, "full-time", db, allow_empty_plan=False
        ) == (True, None)


@pytest.mark.unit
class TestF1Minimum:
    def test_rejects_eleven_credits(self, db) -> None:
        ok, message = check_visa_compliance(
            "international", 11, ["ENG 101"], db, allow_empty_plan=False
        )

        assert ok is False
        assert message is not None
        assert "at least 12 credits" in message
        assert "11 credits" in message

    def test_accepts_twelve_credits(self, db) -> None:
        assert check_visa_compliance(
            "international", 12, ["ENG 101"], db, allow_empty_plan=False
        ) == (True, None)

    def test_empty_finished_plan_fails(self, db) -> None:
        ok, _ = check_visa_compliance("international", 0, [], db, allow_empty_plan=False)

        assert ok is False
