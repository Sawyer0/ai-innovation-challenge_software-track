"""Fixtures for the transcript upload tests."""

import pytest

from tests.conftest import FakeProvider


@pytest.fixture
def groq_like(monkeypatch) -> FakeProvider:
    """A single provider without PDF input, like the production Groq setup."""
    provider = FakeProvider("groq", reads_pdf=False, max_images=3)
    monkeypatch.setattr("app.parsers.transcript_parser.get_providers", lambda: [provider])
    return provider


@pytest.fixture
def session_id(client) -> str:
    return client.post("/api/session").json()["session_id"]
