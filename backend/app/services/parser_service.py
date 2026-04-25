from typing import List, Dict, Any
from fastapi import UploadFile
from ..parsers.file_detector import detect_and_parse
from ..parsers.validators import deduplicate_courses, normalize_course_code
from .session_service import SessionService


class ParserService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    async def parse_upload(self, file: UploadFile) -> Dict[str, Any]:
        """
        Parse uploaded file (auto-detect type) and return structured data.
        
        Returns:
            Dict with source, confidence, student, courses, etc.
        """
        result = await detect_and_parse(file)
        return result

    async def parse_and_save(
        self, 
        file: UploadFile, 
        session_id: str,
        confirm: bool = False
    ) -> Dict[str, Any]:
        """
        Parse uploaded file and optionally save to session.
        
        Two-step flow:
        1. POST /upload (confirm=False) - parse only, return preview
        2. POST /upload/confirm (confirm=True) - parse and save
        
        Args:
            file: Uploaded file (PDF, image, CSV)
            session_id: Student session ID
            confirm: If True, save courses to session
            
        Returns:
            Parsed data with save status
        """
        result = await self.parse_upload(file)
        
        # Add source to each course
        all_courses = result.get("all_courses", [])
        source = result.get("source", "unknown")
        for course in all_courses:
            course["source"] = source
        
        # Save if confirmed
        if confirm and all_courses:
            self.session_service.add_courses_bulk(session_id, all_courses)
            result["saved"] = True
            result["saved_count"] = len(all_courses)
        else:
            result["saved"] = False
            result["saved_count"] = 0
        
        return result

    async def confirm_and_save(
        self,
        courses: List[Dict[str, Any]],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Confirm and save courses from previous parse.
        
        Args:
            courses: List of course dicts to save
            session_id: Student session ID
            
        Returns:
            Save status
        """
        if not courses:
            return {"saved": False, "saved_count": 0, "message": "No courses to save"}
        
        # Deduplicate and normalize
        deduplicated = deduplicate_courses(courses)
        
        # Save to session
        self.session_service.add_courses_bulk(session_id, deduplicated)
        
        return {
            "saved": True,
            "saved_count": len(deduplicated),
            "message": f"Successfully saved {len(deduplicated)} courses"
        }
