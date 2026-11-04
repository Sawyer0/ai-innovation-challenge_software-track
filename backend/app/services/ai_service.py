"""Course advisement generation: Claude first, Gemini as a fallback."""

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from ..academics import calculate_remaining_credits, get_next_semester
from ..config import settings
from ..infrastructure.ai import get_claude_client, get_gemini_client, parse_json_response
from ..models import StudentProfile
from ..prompts import (
    ADVISEMENT_SYSTEM_PROMPT,
    ADVISEMENT_USER_PROMPT_TEMPLATE,
)
from ..schemas import AdvisementResponse, RecommendedCourse

logger = logging.getLogger(__name__)


class AdvisementGenerationError(RuntimeError):
    """Raised when neither AI provider returns a usable advisement."""


def _parse_advisement(
    raw: dict[str, Any], next_semester: str, planned_credits: float
) -> AdvisementResponse:
    courses = [
        RecommendedCourse(
            course_code=c["course_code"],
            course_title=c["course_title"],
            credits=float(c["credits"]),
            requirement_satisfied=c["requirement_satisfied"],
            compliance_status=c["compliance_status"],
            compliance_note=c.get("compliance_note"),
            career_rationale=c["career_rationale"],
            why_now=c["why_now"],
        )
        for c in raw.get("recommended_courses", [])
    ]
    return AdvisementResponse(
        next_semester=next_semester,
        total_planned_credits=planned_credits,
        compliance_cleared=True,
        advisor_message=raw.get("advisor_message", ""),
        recommended_courses=courses,
    )


class AIService:
    """Service for AI-powered advisement generation."""

    async def generate_advisement(
        self,
        profile: StudentProfile,
        completed_courses: list[str],
        in_progress_courses: list[str],
        planned_courses: list[str],
        available_courses: list[dict[str, str]],
        warnings: list[str],
        current_planned_credits: float,
        db: Session,
        student_message: str | None = None,
    ) -> AdvisementResponse:
        """Generate personalized course advisement using imported prompts."""

        # Calculate dynamic values
        next_semester = get_next_semester()
        remaining_credits = calculate_remaining_credits(
            enrollment_status=profile.enrollment_status,
            current_planned_credits=current_planned_credits,
            db=db,
        )
        career_goal = getattr(profile, "career_goal", None) or "Not specified"

        user_prompt = ADVISEMENT_USER_PROMPT_TEMPLATE.format(
            enrollment_status=profile.enrollment_status,
            student_type=profile.student_type,
            classification=profile.classification,
            academic_standing=profile.academic_standing,
            financial_aid_type=profile.financial_aid_type or "None",
            program_code=profile.program_code,
            graduation_semester=profile.graduation_semester,
            graduation_year=profile.graduation_year,
            career_goal=career_goal,
            completed_courses=", ".join(completed_courses) if completed_courses else "None",
            in_progress_courses=", ".join(in_progress_courses) if in_progress_courses else "None",
            planned_courses=", ".join(planned_courses) if planned_courses else "None",
            available_courses="\n".join(
                [f"- {c['code']}: {c['title']}" for c in available_courses]
            ),
            next_semester=next_semester,
            remaining_credits=remaining_credits,
            warnings=", ".join(warnings) if warnings else "All compliance checks passed.",
            student_message=student_message or "What should I take next?",
        )

        for provider in (self._call_claude, self._call_gemini):
            raw = await provider(user_prompt)
            if raw is None:
                continue
            try:
                return _parse_advisement(raw, next_semester, current_planned_credits)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Malformed advisement from %s: %s", provider.__name__, e)

        raise AdvisementGenerationError(
            "Advisement generation failed: neither Claude nor Gemini returned a usable plan."
        )

    async def _call_claude(self, user_prompt: str) -> dict[str, Any] | None:
        try:
            message = await asyncio.to_thread(
                get_claude_client().messages.create,
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                system=ADVISEMENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            result: dict[str, Any] = parse_json_response(message.content[0].text)
            return result
        except Exception as e:
            logger.warning("Claude advisement failed, trying Gemini: %s", e)
            return None

    async def _call_gemini(self, user_prompt: str) -> dict[str, Any] | None:
        try:
            response = await asyncio.to_thread(
                get_gemini_client().models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=[ADVISEMENT_SYSTEM_PROMPT, user_prompt],
            )
            result: dict[str, Any] = parse_json_response(response.text or "")
            return result
        except Exception as e:
            logger.warning("Gemini advisement failed: %s", e)
            return None
