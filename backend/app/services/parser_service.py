from typing import Dict, Any
from fastapi import UploadFile
from ..parsers.transcript_parser import parse_transcript
from .session_service import SessionService


class ParserService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    async def parse_and_save(
        self,
        file: UploadFile,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Parse uploaded transcript and return {profile, courses}.
        Filters out entries without a course_code to avoid DB constraint errors.
        """
        result = await parse_transcript(file)

        # Filter out any course rows that are missing a course_code
        courses = [c for c in result.get("courses", []) if c.get("course_code")]
        result["courses"] = courses

        return result
