import json
from fastapi import UploadFile
from ..prompts import (
    TRANSCRIPT_PARSING_SYSTEM_PROMPT,
    TRANSCRIPT_PARSING_USER_PROMPT,
)
from ..infrastructure.ai import get_ai_client
from ..utils.ai_helpers import clean_json_response


async def parse_transcript(file: UploadFile) -> list:
    """
    Parses a student transcript (image or pdf) using Gemini 2.5 Flash
    and returns a structured list of completed courses.
    Uses centralized prompts from prompts module.
    """
    ai_client = get_ai_client()

    file_content = await file.read()

    # Reset file pointer for any subsequent reads
    await file.seek(0)

    mime_type = file.content_type

    try:
        response_text = ai_client.generate_content(
            contents=[
                TRANSCRIPT_PARSING_SYSTEM_PROMPT,
                {"mime_type": mime_type, "data": file_content},
                TRANSCRIPT_PARSING_USER_PROMPT
            ]
        )

        # Clean up response to ensure it's valid JSON
        json_text = clean_json_response(response_text)
        parsed_courses = json.loads(json_text)
        return parsed_courses
    except Exception as e:
        print(f"Error parsing transcript: {e}")
        raise Exception(f"Failed to parse transcript: {e}")
