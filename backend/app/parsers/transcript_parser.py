import csv
import io
import logging
from typing import Any

from fastapi import UploadFile

from ..infrastructure.ai import get_providers, parse_json_response
from ..prompts import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)
from .validators import validate_course_codes

logger = logging.getLogger(__name__)

TRANSCRIPT_MAX_TOKENS = 4096

SUPPORTED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}


class TranscriptParsingError(RuntimeError):
    """Raised when neither AI provider could read the transcript."""


def _normalize_result(raw: Any) -> dict[str, Any]:
    """
    Normalize the AI response into {profile, courses}.
    Handles the new structured format, bare-array responses, and partial/null fields.
    """
    if isinstance(raw, list):
        return {"profile": {}, "courses": raw}

    if not isinstance(raw, dict):
        return {"profile": {}, "courses": []}

    courses = raw.get("courses") or []
    if not isinstance(courses, list):
        courses = []

    profile = raw.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}

    return {"profile": profile, "courses": courses}


async def parse_transcript(file: UploadFile) -> dict[str, Any]:
    """
    Parse a student transcript into {profile: {...}, courses: [...]}.
    Tries each configured provider in order; raises if none can read it.
    """
    file_content = await file.read()
    await file.seek(0)
    mime_type = file.content_type or ""
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type {mime_type or 'unknown'}; upload a PDF or an image."
        )

    for provider in get_providers():
        try:
            text = await provider.read_document(
                TRANSCRIPT_PARSING_SYSTEM_PROMPT,
                TRANSCRIPT_PARSING_USER_PROMPT,
                file_content,
                mime_type,
                max_tokens=TRANSCRIPT_MAX_TOKENS,
            )
            result = _normalize_result(parse_json_response(text))
            logger.info("Transcript parsed via %s", provider.name)
            return result
        except Exception as e:
            logger.warning("Transcript parsing via %s failed: %s", provider.name, e)

    raise TranscriptParsingError(
        "Transcript parsing failed: no configured AI provider could read the file."
    )


async def parse_transcript_csv(file: UploadFile) -> dict[str, Any]:
    """
    Parse CSV transcript file.
    Expected columns: course_code, course_title, semester_taken, credits, grade, status
    """
    content = await file.read()
    await file.seek(0)

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

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
            "confidence": 1.0,  # CSV data is explicit
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
                c
                for c in valid_courses
                if c.get("status") in ["completed", "passed"] or c.get("grade")
            ],
            "in_progress": [
                c
                for c in valid_courses
                if c.get("status") in ["in_progress", "enrolled"] or not c.get("grade")
            ],
            "still_needed": [],
            "fall_through": [],
        },
        "all_courses": valid_courses,
        "requirements": [],
        "validated": valid_courses,
        "flagged": [],
        "invalid": invalid_courses,
        "requires_confirmation": len(invalid_courses) > 0,
    }
