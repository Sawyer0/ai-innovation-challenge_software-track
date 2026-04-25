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


async def _parse_with_claude(file_content: bytes, mime_type: str) -> list:
    client = _get_claude_client()

    # PDFs use the document block type; images use the image block type
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
        max_tokens=2048,
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

    return json.loads(_clean_json(message.content[0].text))


async def _parse_with_gemini(file_content: bytes, mime_type: str) -> list:
    client = _get_gemini_client()

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            TRANSCRIPT_PARSING_SYSTEM_PROMPT,
            {"mime_type": mime_type, "data": file_content},
            TRANSCRIPT_PARSING_USER_PROMPT,
        ],
    )

    return json.loads(_clean_json(response.text))


async def parse_transcript(file: UploadFile) -> list:
    """
    Parse a student transcript (image or PDF) into a structured course list.
    Tries Claude first, falls back to Gemini, raises if both fail.
    """
    file_content = await file.read()
    await file.seek(0)
    mime_type = file.content_type

    try:
        courses = await _parse_with_claude(file_content, mime_type)
        print("Transcript parsed via Claude")
        return courses
    except Exception as claude_err:
        print(f"Claude parsing failed: {claude_err} — trying Gemini")

    try:
        courses = await _parse_with_gemini(file_content, mime_type)
        print("Transcript parsed via Gemini (fallback)")
        return courses
    except Exception as gemini_err:
        print(f"Gemini parsing failed: {gemini_err}")

    raise Exception("Transcript parsing failed: both Claude and Gemini were unable to process the file.")
