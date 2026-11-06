"""LLM providers behind one small interface.

Every provider can complete a text prompt, read an uploaded document, and read a
batch of page images. Providers without PDF input (``reads_pdf = False``) get PDFs
as text or page images from the caller (see ``documents.py``). ``get_providers()`` returns the ones that have an API key configured, in
fallback order: Claude, Gemini, then Groq (free tier). Tests replace it with fakes.
"""

import asyncio
import base64
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
from google.genai import types as genai_types

from ...config import settings
from .client import get_claude_client, get_gemini_client

REQUEST_TIMEOUT_SECONDS = 50

MISSING_KEY_MESSAGE = (
    "No AI provider is configured. Set GROQ_API_KEY (free at https://console.groq.com/keys), "
    "ANTHROPIC_API_KEY or GEMINI_API_KEY in backend/.env; see backend/.env.example."
)


class NoProviderConfiguredError(RuntimeError):
    """Raised when no LLM provider has an API key."""

    def __init__(self) -> None:
        super().__init__(MISSING_KEY_MESSAGE)


class LLMProvider(Protocol):
    name: str
    # False when the API takes no PDF input, so callers send text or page images.
    reads_pdf: bool
    max_images_per_request: int

    async def complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        """Answer a text prompt."""
        ...

    async def read_document(
        self, system: str, prompt: str, data: bytes, mime_type: str, *, max_tokens: int
    ) -> str:
        """Answer a prompt about an uploaded PDF or image."""
        ...

    async def read_images(
        self, system: str, prompt: str, images: Sequence[bytes], mime_type: str, *, max_tokens: int
    ) -> str:
        """Answer a prompt about several images (e.g. rendered PDF pages) in one request."""
        ...


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


class ClaudeProvider:
    name = "claude"
    reads_pdf = True
    max_images_per_request = 20

    async def complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        return await self._send(system, prompt, max_tokens)

    async def read_document(
        self, system: str, prompt: str, data: bytes, mime_type: str, *, max_tokens: int
    ) -> str:
        block_type = "document" if mime_type == "application/pdf" else "image"
        content = [
            {
                "type": block_type,
                "source": {"type": "base64", "media_type": mime_type, "data": _b64(data)},
            },
            {"type": "text", "text": prompt},
        ]
        return await self._send(system, content, max_tokens)

    async def read_images(
        self, system: str, prompt: str, images: Sequence[bytes], mime_type: str, *, max_tokens: int
    ) -> str:
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": _b64(image)},
            }
            for image in images
        ]
        content.append({"type": "text", "text": prompt})
        return await self._send(system, content, max_tokens)

    async def _send(self, system: str, content: Any, max_tokens: int) -> str:
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


class GeminiProvider:
    name = "gemini"
    reads_pdf = True
    max_images_per_request = 20

    async def complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        return await self._send([system, prompt])

    async def read_document(
        self, system: str, prompt: str, data: bytes, mime_type: str, *, max_tokens: int
    ) -> str:
        return await self._send(
            [system, genai_types.Part.from_bytes(data=data, mime_type=mime_type), prompt]
        )

    async def read_images(
        self, system: str, prompt: str, images: Sequence[bytes], mime_type: str, *, max_tokens: int
    ) -> str:
        parts = [genai_types.Part.from_bytes(data=image, mime_type=mime_type) for image in images]
        return await self._send([system, *parts, prompt])

    async def _send(self, contents: list[Any]) -> str:
        client = get_gemini_client()
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(model=settings.GEMINI_MODEL, contents=contents)
        )
        return response.text or ""


class GroqProvider:
    """Groq's OpenAI-compatible chat completions API.

    Text goes to GROQ_MODEL and images to GROQ_VISION_MODEL. Groq takes no PDF
    input, so callers send a PDF's text layer or its rendered pages instead.
    """

    name = "groq"
    reads_pdf = False
    # GROQ_VISION_MODEL (qwen3.8-27b) accepts at most 3 images per request.
    max_images_per_request = 3

    def __init__(self, api_key: str, http: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._http = http

    async def complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        return await self._chat(settings.GROQ_MODEL, messages, max_tokens)

    async def read_document(
        self, system: str, prompt: str, data: bytes, mime_type: str, *, max_tokens: int
    ) -> str:
        if mime_type == "application/pdf":
            raise ValueError("Groq takes no PDF input; send the PDF's text or page images.")
        return await self.read_images(system, prompt, [data], mime_type, max_tokens=max_tokens)

    async def read_images(
        self, system: str, prompt: str, images: Sequence[bytes], mime_type: str, *, max_tokens: int
    ) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{_b64(image)}"}}
            for image in images
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]
        return await self._chat(settings.GROQ_VISION_MODEL, messages, max_tokens)

    async def _chat(self, model: str, messages: list[dict[str, Any]], max_tokens: int) -> str:
        payload = {"model": model, "messages": messages, "max_completion_tokens": max_tokens}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions"
        if self._http is not None:
            response = await self._http.post(url, json=payload, headers=headers)
        else:
            # Under the 60 s Vercel function limit, so a slow call fails with a clear message.
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.post(url, json=payload, headers=headers)
        response.raise_for_status()
        content: str | None = response.json()["choices"][0]["message"].get("content")
        return content or ""


def get_providers() -> list[LLMProvider]:
    """Configured providers in fallback order. Raises if none has a key."""
    providers: list[LLMProvider] = []
    if settings.has_anthropic_key:
        providers.append(ClaudeProvider())
    if settings.has_gemini_key:
        providers.append(GeminiProvider())
    if settings.has_groq_key:
        providers.append(GroqProvider(settings.GROQ_API_KEY))
    if not providers:
        raise NoProviderConfiguredError()
    return providers
