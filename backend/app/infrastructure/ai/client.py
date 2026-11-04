"""SDK clients for Claude and Gemini, created once per process."""

from functools import cache
from typing import Any

import anthropic
from google import genai

from ...config import settings


@cache
def get_claude_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


@cache
def get_gemini_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)


class AIClient:
    """Thin Gemini wrapper used by the DegreeWorks parser."""

    @property
    def model(self) -> str:
        return settings.GEMINI_MODEL

    def generate_content(self, contents: list[Any], model: str | None = None, **kwargs: Any) -> str:
        response = get_gemini_client().models.generate_content(
            model=model or self.model, contents=contents, **kwargs
        )
        return response.text or ""


@cache
def get_ai_client() -> AIClient:
    return AIClient()
