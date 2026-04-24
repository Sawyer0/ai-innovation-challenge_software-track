from google import genai
from ..config import settings
from ..models import StudentProfile
from typing import List, Optional
from sqlalchemy.orm import Session
from ..prompts import (
    ADVISEMENT_SYSTEM_PROMPT,
    ADVISEMENT_USER_PROMPT_TEMPLATE,
)
from ..utils import get_next_semester, calculate_remaining_credits

class AIService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL

    async def generate_advisement(self,
                                  profile: StudentProfile,
                                  completed_courses: List[str],
                                  in_progress_courses: List[str],
                                  planned_courses: List[str],
                                  available_courses: List[dict],
                                  warnings: List[str],
                                  current_planned_credits: float,
                                  db: Session,
                                  student_message: Optional[str] = None) -> str:
        """Generate personalized course advisement using imported prompts."""

        # Calculate dynamic values
        next_semester = get_next_semester()
        remaining_credits = calculate_remaining_credits(
            enrollment_status=profile.enrollment_status,
            current_planned_credits=current_planned_credits,
            db=db
        )

        user_prompt = ADVISEMENT_USER_PROMPT_TEMPLATE.format(
            enrollment_status=profile.enrollment_status,
            student_type=profile.student_type,
            financial_aid_type=profile.financial_aid_type or "None",
            program_code=profile.program_code,
            graduation_semester=profile.graduation_semester,
            graduation_year=profile.graduation_year,
            completed_courses=", ".join(completed_courses) if completed_courses else "None",
            in_progress_courses=", ".join(in_progress_courses) if in_progress_courses else "None",
            planned_courses=", ".join(planned_courses) if planned_courses else "None",
            available_courses="\n".join([f"- {c['code']}: {c['title']}" for c in available_courses]),
            next_semester=next_semester,
            remaining_credits=remaining_credits,
            warnings="\n".join(warnings) if warnings else "No warnings",
            student_message=student_message or "What should I take next?"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    ADVISEMENT_SYSTEM_PROMPT,
                    user_prompt
                ]
            )
            return response.text
        except Exception as e:
            return f"Error generating advisement: {e}"
