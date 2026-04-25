import base64
import json
import anthropic
from google import genai
from google.genai import types as genai_types
from ..config import settings
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

_claude_client = None
_gemini_client = None


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
    """Strip markdown code fences from an LLM JSON response."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


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
    client = _get_claude_client()

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

    message = client.messages.create(
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

    raw = json.loads(_clean_json(message.content[0].text))
    return _normalize_result(raw)


async def _parse_with_gemini(file_content: bytes, mime_type: str) -> dict:
    client = _get_gemini_client()

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            TRANSCRIPT_PARSING_SYSTEM_PROMPT,
            genai_types.Part.from_bytes(data=file_content, mime_type=mime_type),
            TRANSCRIPT_PARSING_USER_PROMPT,
        ],
    )

    raw = json.loads(_clean_json(response.text))
    return _normalize_result(raw)


async def parse_transcript(file: UploadFile) -> dict:
    """
    Parse a student transcript into {profile: {...}, courses: [...]}.
    Tries Claude first, falls back to Gemini, raises if both fail.
    """
    file_content = await file.read()
    await file.seek(0)
    mime_type = file.content_type

    try:
        result = await _parse_with_claude(file_content, mime_type)
        print("Transcript parsed via Claude")
        return result
    except Exception as claude_err:
        print(f"Claude parsing failed: {claude_err} — trying Gemini")

    try:
        result = await _parse_with_gemini(file_content, mime_type)
        print("Transcript parsed via Gemini (fallback)")
        return result
    except Exception as gemini_err:
        print(f"Gemini parsing failed: {gemini_err}")

    raise Exception("Transcript parsing failed: both Claude and Gemini were unable to process the file.")

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
