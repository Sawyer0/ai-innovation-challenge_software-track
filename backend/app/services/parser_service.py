from typing import List, Dict, Any
from fastapi import UploadFile
from ..parsers.transcript_parser import parse_transcript
from .session_service import SessionService

class ParserService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    async def parse_and_save(self, file: UploadFile, session_id: str) -> Dict[str, Any]:
        """
        Parse transcript and save courses to the session.
        Returns {profile: {...}, courses: [...]} — profile contains hints
        extracted from the transcript header (school, program, GPA, etc.)
        that the frontend can use to prefill the profile form.
        """
        result = await parse_transcript(file)
        courses = result.get("courses", [])
        profile_hints = result.get("profile", {}) or {}

        for course in courses:
            course["source"] = "transcript"

        self.session_service.add_courses_bulk(session_id, courses)

        return {"profile": profile_hints, "courses": courses}
