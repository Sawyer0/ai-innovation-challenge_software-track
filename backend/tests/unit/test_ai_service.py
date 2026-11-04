"""
Unit tests for AIService: prompt building, provider fallback and
response parsing. Providers are the fakes from conftest; nothing leaves the box.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.ai import NoProviderConfiguredError, strip_code_fences
from app.schemas import AdvisementResponse
from app.services.ai_service import AdvisementGenerationError, AIService

PLAN = {
    "advisor_message": "Since you finished MAT 157, Precalculus is the natural next step.",
    "recommended_courses": [
        {
            "course_code": "MAT 206",
            "course_title": "Precalculus",
            "credits": 4,
            "requirement_satisfied": "Required: Year 1 Spring",
            "compliance_status": "compliant",
            "compliance_note": None,
            "career_rationale": "Calculus-track math underpins robotics.",
            "why_now": "Its prerequisite, MAT 157, is complete.",
        }
    ],
}


async def _advise(service: AIService, profile, **overrides) -> AdvisementResponse:
    kwargs = {
        "profile": profile,
        "completed_courses": ["MAT 157", "ENG 101"],
        "in_progress_courses": ["CSC 101"],
        "planned_courses": [],
        "available_courses": [{"code": "MAT 206", "title": "Precalculus"}],
        "warnings": ["Pell Grant: recommend at least 6 credits."],
        "current_planned_credits": 0.0,
        "db": MagicMock(),
        "student_message": "What should I take next?",
    }
    kwargs.update(overrides)
    with (
        patch("app.services.ai_service.get_next_semester", return_value="Fall 2026"),
        patch("app.services.ai_service.calculate_remaining_credits", return_value=18.0),
    ):
        return await service.generate_advisement(**kwargs)


@pytest.mark.unit
class TestGenerateAdvisement:
    async def test_returns_structured_plan_from_first_provider(self, mock_profile, ai_providers):
        ai_providers.primary.queue(PLAN)

        result = await _advise(AIService(), mock_profile)

        assert result.next_semester == "Fall 2026"
        assert result.compliance_cleared is True
        assert [c.course_code for c in result.recommended_courses] == ["MAT 206"]
        assert result.recommended_courses[0].credits == 4.0
        assert ai_providers.fallback.calls == []

    async def test_prompt_includes_student_context(self, mock_profile, ai_providers):
        ai_providers.primary.queue(PLAN)

        await _advise(AIService(), mock_profile)

        prompt = ai_providers.primary.calls[0]["prompt"]
        for expected in (
            "MAT 157, ENG 101",
            "CSC 101",
            "- MAT 206: Precalculus",
            "pell",
            "CSC-AS",
            "Fall 2026",
            "Pell Grant: recommend at least 6 credits.",
            "What should I take next?",
        ):
            assert expected in prompt

    async def test_empty_history_and_default_message(self, mock_profile, ai_providers):
        ai_providers.primary.queue(PLAN)

        await _advise(
            AIService(),
            mock_profile,
            completed_courses=[],
            in_progress_courses=[],
            warnings=[],
            student_message=None,
        )

        prompt = ai_providers.primary.calls[0]["prompt"]
        assert "None" in prompt
        assert "All compliance checks passed." in prompt
        assert "What should I take next?" in prompt

    async def test_falls_back_when_first_provider_fails(self, mock_profile, ai_providers):
        ai_providers.fallback.queue("```json\n" + json.dumps(PLAN) + "\n```")

        result = await _advise(AIService(), mock_profile)

        assert len(ai_providers.primary.calls) == 1
        assert len(ai_providers.fallback.calls) == 1
        assert result.recommended_courses[0].course_code == "MAT 206"

    async def test_falls_back_when_first_reply_is_malformed(self, mock_profile, ai_providers):
        ai_providers.primary.queue({"recommended_courses": [{"course_code": "MAT 206"}]})
        ai_providers.fallback.queue(PLAN)

        result = await _advise(AIService(), mock_profile)

        assert result.recommended_courses[0].course_title == "Precalculus"

    async def test_raises_when_every_provider_fails(self, mock_profile, ai_providers):
        ai_providers.primary.queue("not json")
        ai_providers.fallback.queue("still not json")

        with pytest.raises(AdvisementGenerationError):
            await _advise(AIService(), mock_profile)

    async def test_sends_advisement_system_prompt(self, mock_profile, ai_providers):
        from app.prompts import ADVISEMENT_SYSTEM_PROMPT

        ai_providers.primary.queue(PLAN)
        await _advise(AIService(), mock_profile)

        assert ai_providers.primary.calls[0]["system"] == ADVISEMENT_SYSTEM_PROMPT

    async def test_missing_keys_raise_a_clear_error(self, mock_profile, monkeypatch):
        def no_providers():
            raise NoProviderConfiguredError()

        monkeypatch.setattr("app.services.ai_service.get_providers", no_providers)

        with pytest.raises(NoProviderConfiguredError, match="GROQ_API_KEY"):
            await _advise(AIService(), mock_profile)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ("```\n[1, 2]\n```", "[1, 2]"),
        ('  {"a": 1}  ', '{"a": 1}'),
    ],
)
def test_strip_code_fences(raw: str, expected: str) -> None:
    assert strip_code_fences(raw) == expected
