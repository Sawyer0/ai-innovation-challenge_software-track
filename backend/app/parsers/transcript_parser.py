import asyncio
import csv
import io
import logging
import re
from collections.abc import Sequence
from typing import Any

from fastapi import UploadFile

from ..infrastructure.ai import LLMProvider, get_providers, parse_json_response
from ..infrastructure.ai.documents import (
    UnreadableDocumentError,
    extract_pdf_text,
    pdf_text_is_usable,
    render_pdf_pages,
)
from ..infrastructure.ai.errors import (
    TIMEOUT_MESSAGE,
    ProviderFailure,
    busy_message,
    classify_provider_error,
)
from ..infrastructure.ai.redaction import redact_text
from ..prompts import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)
from .validators import validate_course_codes

logger = logging.getLogger(__name__)

TRANSCRIPT_MAX_TOKENS = 4096
PDF = "application/pdf"
PAGE_IMAGE_MIME = "image/jpeg"

SUPPORTED_MIME_TYPES = {PDF, "image/png", "image/jpeg", "image/gif", "image/webp"}

NO_COURSES_MESSAGE = (
    "We couldn't find any courses in this file. Upload your unofficial transcript from "
    "CUNYfirst (PDF) or clear screenshots of it, or skip this step and fill in the form."
)
FAILED_MESSAGE = (
    "We couldn't read this transcript. Try a clearer screenshot or the PDF from CUNYfirst, "
    "or skip this step and fill in the form."
)


class TranscriptParsingError(RuntimeError):
    """No provider could read the transcript. ``str(e)`` is safe to show the visitor."""

    def __init__(self, message: str, status_code: int = 502, retry_after: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


_SEMESTER = re.compile(
    r"^\s*(?:(\d{4})\s+(fall|spring|summer|winter)|(fall|spring|summer|winter)\s+(\d{4}))"
    r"(?:\s+term)?\s*$",
    re.IGNORECASE,
)


def _normalize_semester(value: Any) -> Any:
    """'2026 Fall Term' / 'FALL 2026' -> 'Fall 2026'; anything else is left alone."""
    if not isinstance(value, str):
        return value
    match = _SEMESTER.match(value)
    if not match:
        return value
    year = match.group(1) or match.group(4)
    term = match.group(2) or match.group(3)
    return f"{term.capitalize()} {year}"


def _normalize_course(course: dict[str, Any]) -> dict[str, Any]:
    """Treat a course with no grade as in progress (CUNYfirst lists current-term
    courses with no grade and 0 earned credits); its credits then aren't known yet."""
    grade = course.get("grade")
    grade = grade.strip() if isinstance(grade, str) else grade
    if not grade or (isinstance(grade, str) and grade.upper() == "IP"):
        grade = None
    course["grade"] = grade
    course["semester_taken"] = _normalize_semester(course.get("semester_taken"))
    status = course.get("status")
    if status != "withdrawn" and grade is None:
        course["status"] = "in-progress"
    if course.get("status") == "in-progress" and not course.get("credits"):
        course["credits"] = None  # filled from the catalog by ParserService
    return course


# Only these fields leave the parser. Anything else a model returns (a name or a
# student ID read off the page, say) is dropped.
PROFILE_FIELDS = (
    "school",
    "program_code",
    "program_name",
    "degree",
    "student_type",
    "cumulative_gpa",
    "total_credits_earned",
    "total_credits_needed",
)
COURSE_FIELDS = ("course_code", "course_title", "semester_taken", "credits", "grade", "status")


def _normalize_result(raw: Any) -> dict[str, Any]:
    """
    Normalize the AI response into {profile, courses}.
    Handles the new structured format, bare-array responses, and partial/null fields.
    """
    if isinstance(raw, list):
        raw = {"courses": raw}

    if not isinstance(raw, dict):
        return {"profile": {}, "courses": []}

    courses = raw.get("courses") or []
    if not isinstance(courses, list):
        courses = []

    profile = raw.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}

    return {
        "profile": {key: profile[key] for key in PROFILE_FIELDS if key in profile},
        "courses": [
            _normalize_course({key: c.get(key) for key in COURSE_FIELDS})
            for c in courses
            if isinstance(c, dict)
        ],
    }


def _merge_results(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Merge per-page-batch results: first non-null profile field wins, courses deduped."""
    profile: dict[str, Any] = {}
    courses: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for result in results:
        for key, value in result["profile"].items():
            if profile.get(key) is None:
                profile[key] = value
        for course in result["courses"]:
            key = (course.get("course_code"), course.get("semester_taken"))
            if key not in seen:
                seen.add(key)
                courses.append(course)
    return {"profile": profile, "courses": courses}


async def _read_pages(provider: LLMProvider, pages: list[bytes]) -> dict[str, Any]:
    """Send rendered pages in batches the provider accepts, concurrently, and merge."""
    size = max(1, provider.max_images_per_request)
    batches = [pages[i : i + size] for i in range(0, len(pages), size)]
    replies = await asyncio.gather(
        *(
            provider.read_images(
                TRANSCRIPT_PARSING_SYSTEM_PROMPT,
                TRANSCRIPT_PARSING_USER_PROMPT,
                batch,
                PAGE_IMAGE_MIME,
                max_tokens=TRANSCRIPT_MAX_TOKENS,
            )
            for batch in batches
        )
    )
    return _merge_results([_normalize_result(parse_json_response(r)) for r in replies])


async def _read_with(provider: LLMProvider, data: bytes, mime_type: str) -> dict[str, Any]:
    if mime_type != PDF:
        # A screenshot has no text to find identifiers in; see redaction.py.
        text = await provider.read_document(
            TRANSCRIPT_PARSING_SYSTEM_PROMPT,
            TRANSCRIPT_PARSING_USER_PROMPT,
            data,
            mime_type,
            max_tokens=TRANSCRIPT_MAX_TOKENS,
        )
        return _normalize_result(parse_json_response(text))

    # A PDF is never sent as-is, even to providers that take PDFs: it goes as its
    # text layer with identifiers redacted, or as page images with them blacked out.
    pdf_text = extract_pdf_text(data)
    if pdf_text_is_usable(pdf_text):
        text = await provider.complete(
            TRANSCRIPT_PARSING_SYSTEM_PROMPT,
            f"{TRANSCRIPT_PARSING_USER_PROMPT}\n\n--- Document text ---\n{redact_text(pdf_text)}",
            max_tokens=TRANSCRIPT_MAX_TOKENS,
        )
        result = _normalize_result(parse_json_response(text))
        if result["courses"]:
            return result
        logger.info("Text layer gave no courses via %s; reading page images", provider.name)
    else:
        logger.info("PDF text layer unusable (%d chars); reading page images", len(pdf_text))
    return await _read_pages(provider, render_pdf_pages(data))


def _error_for(failures: list[ProviderFailure]) -> TranscriptParsingError:
    busy = [f for f in failures if f.kind == "busy"]
    if busy and len(busy) == len(failures):
        retry_after = min(f.retry_after or 30 for f in busy)
        return TranscriptParsingError(busy_message(retry_after), 503, retry_after)
    if any(f.kind == "timeout" for f in failures):
        return TranscriptParsingError(TIMEOUT_MESSAGE, 504)
    return TranscriptParsingError(FAILED_MESSAGE, 502)


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

    failures: list[ProviderFailure] = []
    empty_result: dict[str, Any] | None = None
    for provider in get_providers():
        try:
            result = await _read_with(provider, file_content, mime_type)
        except UnreadableDocumentError:
            raise
        except Exception as e:
            failure = classify_provider_error(e)
            failures.append(failure)
            # The error type only: provider messages can quote the request.
            logger.warning(
                "Transcript parsing via %s failed (%s): %s",
                provider.name,
                failure.kind,
                type(e).__name__,
            )
            continue
        if result["courses"]:
            logger.info("Transcript parsed via %s", provider.name)
            return result
        empty_result = result
        logger.warning("Transcript via %s returned no courses", provider.name)

    if empty_result is not None:
        raise TranscriptParsingError(NO_COURSES_MESSAGE, 422)
    raise _error_for(failures)


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
