"""Shared clients for the AI providers (Claude primary, Gemini fallback)."""

import asyncio
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


async def claude_complete(system: str, content: Any, max_tokens: int) -> str:
    """Send one user turn to Claude in a worker thread and return its text."""
    client = get_claude_client()
    message = await asyncio.to_thread(
        lambda: client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
    )
    return "".join(getattr(block, "text", "") for block in message.content)


async def gemini_complete(contents: list[Any]) -> str:
    """Ask Gemini in a worker thread and return its text."""
    client = get_gemini_client()
    response = await asyncio.to_thread(
        lambda: client.models.generate_content(model=settings.GEMINI_MODEL, contents=contents)
    )
    return response.text or ""


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
