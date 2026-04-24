from typing import List, Dict, Any
from fastapi import UploadFile
from ..parsers.transcript_parser import parse_transcript
from .session_service import SessionService

class ParserService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    async def parse_and_save(self, file: UploadFile, session_id: str) -> List[Dict[str, Any]]:
        parsed_courses = await parse_transcript(file)
        # Add source field to identify courses from transcript
        for course in parsed_courses:
            course["source"] = "transcript"
        self.session_service.add_courses_bulk(session_id, parsed_courses)
        return parsed_courses
