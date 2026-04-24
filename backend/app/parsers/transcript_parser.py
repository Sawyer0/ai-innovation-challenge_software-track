import os
import json
from google import genai
from ..config import settings
from fastapi import UploadFile
from ..prompts import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)

# Initialize Gemini client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def parse_transcript(file: UploadFile):
    """
    Parses a student transcript (image or pdf) using Gemini 2.5 Flash
    and returns a structured list of completed courses.
    Uses centralized prompts from prompts module.
    """
    file_content = await file.read()

    # Reset file pointer for any subsequent reads
    await file.seek(0)

    mime_type = file.content_type

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                TRANSCRIPT_PARSING_SYSTEM_PROMPT,
                {"mime_type": mime_type, "data": file_content},
                TRANSCRIPT_PARSING_USER_PROMPT
            ]
        )

        # Clean up response to ensure it's valid JSON
        json_text = response.text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]

        parsed_courses = json.loads(json_text)
        return parsed_courses
    except Exception as e:
        print(f"Error parsing transcript: {e}")
        raise Exception(f"Failed to parse transcript: {e}")
