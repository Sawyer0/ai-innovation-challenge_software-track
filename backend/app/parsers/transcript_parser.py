import csv
import io
import json
from typing import Dict, Any, List
from fastapi import UploadFile
from ..prompts import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)
from ..infrastructure.ai import get_ai_client, AIError
from ..utils.ai_helpers import safe_json_parse
from .validators import validate_course_codes, flag_low_confidence_courses


async def parse_transcript(file: UploadFile) -> Dict[str, Any]:
    """
    Parses a student transcript (image or pdf) using Gemini 2.5 Flash
    and returns structured data with confidence scores.
    """
    ai_client = get_ai_client()

    file_content = await file.read()
    await file.seek(0)

    mime_type = file.content_type or "application/octet-stream"

    try:
        response_text = ai_client.generate_content(
            contents=[
                TRANSCRIPT_PARSING_SYSTEM_PROMPT,
                {"mime_type": mime_type, "data": file_content},
                TRANSCRIPT_PARSING_USER_PROMPT
            ]
        )

        # Parse JSON response
        parsed_courses = safe_json_parse(response_text, default=[])
        
        if not isinstance(parsed_courses, list):
            parsed_courses = []
        
        # Validate course codes
        valid_courses, invalid_courses = validate_course_codes(parsed_courses)
        
        # Flag low confidence items
        flagged = flag_low_confidence_courses(valid_courses, threshold=0.7)
        
        # Calculate confidence
        avg_confidence = sum(
            c.get("confidence", 0.8) for c in valid_courses
        ) / len(valid_courses) if valid_courses else 0.0
        
        # Adjust for invalid courses
        invalid_penalty = min(len(invalid_courses) * 0.05, 0.2)
        overall_confidence = max(0.0, avg_confidence - invalid_penalty)
        
        return {
            "source": "transcript",
            "confidence": overall_confidence,
            "student": {},  # Transcripts don't have student info section
            "courses": {
                "completed": [
                    c for c in valid_courses 
                    if c.get("status") in ["completed", "passed"] or c.get("grade")
                ],
                "in_progress": [
                    c for c in valid_courses 
                    if c.get("status") in ["in_progress", "enrolled"] or not c.get("grade")
                ],
                "still_needed": [],
                "fall_through": []
            },
            "all_courses": valid_courses,
            "requirements": [],
            "validated": valid_courses,
            "flagged": flagged,
            "invalid": invalid_courses,
            "requires_confirmation": len(flagged) > 0 or len(invalid_courses) > 0
        }
        
    except AIError as e:
        raise ValueError(f"AI parsing error: {e}")
    except Exception as e:
        raise ValueError(f"Failed to parse transcript: {e}")


async def parse_transcript_csv(file: UploadFile) -> Dict[str, Any]:
    """
    Parse CSV transcript file.
    Expected columns: course_code, course_title, semester_taken, credits, grade, status
    """
    content = await file.read()
    await file.seek(0)
    
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('latin-1')
    
    reader = csv.DictReader(io.StringIO(text))
    courses = []
    
    for row in reader:
        course = {
            "code": row.get("course_code", ""),
            "title": row.get("course_title", ""),
            "semester_taken": row.get("semester_taken", ""),
            "credits": float(row.get("credits", 0)) if row.get("credits") else 0,
            "grade": row.get("grade") or None,
            "status": row.get("status", "completed"),
            "confidence": 1.0  # CSV data is explicit
        }
        courses.append(course)
    
    # Validate
    valid_courses, invalid_courses = validate_course_codes(courses)
    
    return {
        "source": "transcript_csv",
        "confidence": 1.0,
        "student": {},
        "courses": {
            "completed": [
                c for c in valid_courses 
                if c.get("status") in ["completed", "passed"] or c.get("grade")
            ],
            "in_progress": [
                c for c in valid_courses 
                if c.get("status") in ["in_progress", "enrolled"] or not c.get("grade")
            ],
            "still_needed": [],
            "fall_through": []
        },
        "all_courses": valid_courses,
        "requirements": [],
        "validated": valid_courses,
        "flagged": [],
        "invalid": invalid_courses,
        "requires_confirmation": len(invalid_courses) > 0
    }
