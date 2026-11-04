"""
Unit tests for the provider layer: which providers are active, and the Groq
client's request/response handling against a mocked HTTP transport (no network).
"""

import json

import httpx
import pytest

from app.config import settings
from app.infrastructure.ai import providers
from app.infrastructure.ai.providers import (
    GroqProvider,
    NoProviderConfiguredError,
    get_providers,
)


def _keys(monkeypatch, *, anthropic="", gemini="", groq="") -> None:
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", anthropic)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", gemini)
    monkeypatch.setattr(settings, "GROQ_API_KEY", groq)


@pytest.mark.unit
class TestGetProviders:
    def test_no_keys_fails_with_setup_instructions(self, monkeypatch):
        _keys(monkeypatch)

        with pytest.raises(NoProviderConfiguredError) as err:
            get_providers()

        assert "GROQ_API_KEY" in str(err.value)
        assert ".env.example" in str(err.value)

    def test_placeholder_keys_do_not_count(self, monkeypatch):
        _keys(monkeypatch, anthropic="sk-placeholder", groq="gsk_...")

        with pytest.raises(NoProviderConfiguredError):
            get_providers()

    def test_groq_alone_is_enough(self, monkeypatch):
        _keys(monkeypatch, groq="gsk_test")

        assert [p.name for p in get_providers()] == ["groq"]

    def test_fallback_order(self, monkeypatch):
        _keys(monkeypatch, anthropic="sk-ant-test", gemini="g-test", groq="gsk_test")

        assert [p.name for p in get_providers()] == ["claude", "gemini", "groq"]


def _groq(handler) -> tuple[GroqProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(record))
    return GroqProvider("gsk_test", http=http), seen


def _reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@pytest.mark.unit
class TestGroqProvider:
    async def test_complete_posts_openai_style_chat(self):
        groq, seen = _groq(lambda r: _reply('{"ok": true}'))

        text = await groq.complete("system prompt", "user prompt", max_tokens=100)

        assert text == '{"ok": true}'
        request = seen[0]
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer gsk_test"
        body = json.loads(request.content)
        assert body["model"] == settings.GROQ_MODEL
        assert body["max_completion_tokens"] == 100
        assert body["messages"] == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ]

    async def test_images_go_to_the_vision_model_as_data_urls(self):
        groq, seen = _groq(lambda r: _reply("{}"))

        await groq.read_document("sys", "read this", b"\x89PNG", "image/png", max_tokens=50)

        body = json.loads(seen[0].content)
        assert body["model"] == settings.GROQ_VISION_MODEL
        image = body["messages"][1]["content"][1]["image_url"]["url"]
        assert image.startswith("data:image/png;base64,")

    async def test_pdfs_are_sent_as_extracted_text(self, monkeypatch):
        monkeypatch.setattr(providers, "extract_pdf_text", lambda data: "MAT 157  A  4.0")
        groq, seen = _groq(lambda r: _reply("{}"))

        await groq.read_document("sys", "read this", b"%PDF", "application/pdf", max_tokens=50)

        body = json.loads(seen[0].content)
        assert body["model"] == settings.GROQ_MODEL
        assert "MAT 157  A  4.0" in body["messages"][1]["content"]

    async def test_pdf_without_text_layer_is_rejected(self, monkeypatch):
        monkeypatch.setattr(providers, "extract_pdf_text", lambda data: "")
        groq, seen = _groq(lambda r: _reply("{}"))

        with pytest.raises(ValueError, match="no text layer"):
            await groq.read_document("sys", "p", b"%PDF", "application/pdf", max_tokens=50)
        assert seen == []

    async def test_http_errors_raise(self):
        groq, _ = _groq(lambda r: httpx.Response(401, json={"error": "bad key"}))

        with pytest.raises(httpx.HTTPStatusError):
            await groq.complete("sys", "p", max_tokens=10)
