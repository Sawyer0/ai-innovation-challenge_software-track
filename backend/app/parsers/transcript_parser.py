import asyncio
import base64
import csv
import io
import logging
from typing import Any

from fastapi import UploadFile
from google.genai import types as genai_types

from ..config import settings
from ..infrastructure.ai import get_claude_client, get_gemini_client, parse_json_response
from ..prompts import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)
from .validators import validate_course_codes

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}


class TranscriptParsingError(RuntimeError):
    """Raised when neither AI provider could read the transcript."""


def _normalize_result(raw: dict | list) -> dict:
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


async def _parse_with_claude(file_content: bytes, mime_type: str) -> dict:

    if mime_type == "application/pdf":
        content_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(file_content).decode("utf-8"),
            },
        }
    else:
        content_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": base64.standard_b64encode(file_content).decode("utf-8"),
            },
        }

    message = await asyncio.to_thread(
        get_claude_client().messages.create,
        model=settings.CLAUDE_MODEL,
        max_tokens=4096,
        system=TRANSCRIPT_PARSING_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    content_block,
                    {"type": "text", "text": TRANSCRIPT_PARSING_USER_PROMPT},
                ],
            }
        ],
    )

    raw = parse_json_response(message.content[0].text)
    return _normalize_result(raw)


async def _parse_with_gemini(file_content: bytes, mime_type: str) -> dict:
    response = await asyncio.to_thread(
        get_gemini_client().models.generate_content,
        model=settings.GEMINI_MODEL,
        contents=[
            TRANSCRIPT_PARSING_SYSTEM_PROMPT,
            genai_types.Part.from_bytes(data=file_content, mime_type=mime_type),
            TRANSCRIPT_PARSING_USER_PROMPT,
        ],
    )

    raw = parse_json_response(response.text or "")
    return _normalize_result(raw)


async def parse_transcript(file: UploadFile) -> dict:
    """
    Parse a student transcript into {profile: {...}, courses: [...]}.
    Tries Claude first, falls back to Gemini, raises if both fail.
    """
    file_content = await file.read()
    await file.seek(0)
    mime_type = file.content_type or ""
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type {mime_type or 'unknown'}; upload a PDF or an image."
        )

    try:
        result = await _parse_with_claude(file_content, mime_type)
        logger.info("Transcript parsed via Claude")
        return result
    except Exception as claude_err:
        logger.warning("Claude parsing failed, trying Gemini: %s", claude_err)

    try:
        result = await _parse_with_gemini(file_content, mime_type)
        logger.info("Transcript parsed via Gemini (fallback)")
        return result
    except Exception as gemini_err:
        logger.warning("Gemini parsing failed: %s", gemini_err)

    raise TranscriptParsingError(
        "Transcript parsing failed: both Claude and Gemini were unable to process the file."
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
