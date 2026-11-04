"""SDK clients for Claude and Gemini, created once per process."""

from functools import cache

import anthropic
from google import genai

from ...config import settings


@cache
def get_claude_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


@cache
def get_gemini_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)
