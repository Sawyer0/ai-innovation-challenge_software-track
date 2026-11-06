from typing import Any

from fastapi import UploadFile

from ..models import Course
from ..parsers.transcript_parser import parse_transcript
from .session_service import SessionService


class ParserService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    async def parse_and_save(
        self,
        file: UploadFile,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Parse uploaded transcript and return {profile, courses}.
        Filters out entries without a course_code to avoid DB constraint errors.
        """
        result = await parse_transcript(file)

        # Filter out any course rows that are missing a course_code
        courses = [c for c in result.get("courses", []) if c.get("course_code")]
        result["courses"] = courses
        self._fill_missing_credits(courses)

        return result

    def _fill_missing_credits(self, courses: list[dict[str, Any]]) -> None:
        """Use catalog credits for in-progress courses and for any course without credits.

        CUNYfirst shows no earned credits for the current term, and models reading it
        tend to pick up another number on the row (e.g. contact hours) instead.
        """
        db = self.session_service.repo.db
        for course in courses:
            if course.get("credits") and course.get("status") != "in-progress":
                continue
            row = db.query(Course).filter(Course.code == course["course_code"]).first()
            if row is not None and row.credits:
                course["credits"] = float(row.credits)
