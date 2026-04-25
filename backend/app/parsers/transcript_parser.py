import base64
import json
import anthropic
from google import genai
from ..config import settings
from fastapi import UploadFile
from ..prompts import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)

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
    Handles both the new structured format and the legacy bare-array format.
    """
    if isinstance(raw, list):
        # Legacy: AI returned just a courses array
        return {"profile": {}, "courses": raw}

    courses = raw.get("courses", [])
    profile = raw.get("profile", {}) or {}
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
            {"mime_type": mime_type, "data": file_content},
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
