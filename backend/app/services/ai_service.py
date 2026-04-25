import json
import anthropic
from google import genai
from ..config import settings
from ..models import StudentProfile
from ..schemas import AdvisementResponse, RecommendedCourse
from typing import List, Optional
from sqlalchemy.orm import Session
from ..prompts import (
    ADVISEMENT_SYSTEM_PROMPT,
    ADVISEMENT_USER_PROMPT_TEMPLATE,
)
from ..utils import get_next_semester, calculate_remaining_credits

_claude_client: Optional[anthropic.Anthropic] = None
_gemini_client: Optional[genai.Client] = None


def _get_claude_client() -> anthropic.Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _claude_client


def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _parse_advisement(raw: dict, next_semester: str, planned_credits: float) -> AdvisementResponse:
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
    async def generate_advisement(
        self,
        profile: StudentProfile,
        completed_courses: List[str],
        in_progress_courses: List[str],
        planned_courses: List[str],
        available_courses: List[dict],
        warnings: List[str],
        current_planned_credits: float,
        db: Session,
        student_message: Optional[str] = None,
    ) -> AdvisementResponse:

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
            financial_aid_type=profile.financial_aid_type or "None",
            program_code=profile.program_code,
            graduation_semester=profile.graduation_semester,
            graduation_year=profile.graduation_year,
            career_goal=career_goal,
            completed_courses=", ".join(completed_courses) if completed_courses else "None",
            in_progress_courses=", ".join(in_progress_courses) if in_progress_courses else "None",
            planned_courses=", ".join(planned_courses) if planned_courses else "None",
            available_courses="\n".join([f"- {c['code']}: {c['title']}" for c in available_courses]),
            next_semester=next_semester,
            remaining_credits=remaining_credits,
            warnings=", ".join(warnings) if warnings else "All compliance checks passed.",
            student_message=student_message or "What should I take next?",
        )

        raw = await self._call_claude(user_prompt)
        if raw is None:
            raw = await self._call_gemini(user_prompt)
        if raw is None:
            raise Exception("Advisement generation failed: both Claude and Gemini were unable to respond.")

        return _parse_advisement(raw, next_semester, current_planned_credits)

    async def _call_claude(self, user_prompt: str) -> Optional[dict]:
        try:
            client = _get_claude_client()
            message = client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                system=ADVISEMENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return json.loads(_clean_json(message.content[0].text))
        except Exception as e:
            print(f"Claude advisement failed: {e} — trying Gemini")
            return None

    async def _call_gemini(self, user_prompt: str) -> Optional[dict]:
        try:
            client = _get_gemini_client()
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[ADVISEMENT_SYSTEM_PROMPT, user_prompt],
            )
            return json.loads(_clean_json(response.text))
        except Exception as e:
            print(f"Gemini advisement failed: {e}")
            return None
