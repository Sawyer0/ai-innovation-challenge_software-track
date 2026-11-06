"""AI quota reporting: /api/usage, X-AI-* headers, and the global daily cap."""

from importlib import import_module

import pytest

from app.config import settings
from tests.integration.transcript_helpers import course, upload

# The module, not the same-named dependency that app.dependencies re-exports.
limits = import_module("app.dependencies.rate_limit")

pytestmark = pytest.mark.integration


class TestUsage:
    def test_usage_reports_quota_without_consuming_it(self, client):
        first = client.get("/api/usage")
        second = client.get("/api/usage")

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        body = first.json()
        assert body["hour"] == {
            "limit": settings.AI_RATE_LIMIT_PER_HOUR,
            "remaining": settings.AI_RATE_LIMIT_PER_HOUR,
            "reset_seconds": 0,
        }
        assert body["day"]["limit"] == settings.AI_DAILY_LIMIT
        assert body["scope"]["day"] == "global"
        assert first.headers["x-ai-remaining-hour"] == str(settings.AI_RATE_LIMIT_PER_HOUR)

    def test_ai_calls_return_quota_headers_and_update_usage(self, client, session_id, groq_like):
        groq_like.queue({"courses": [course("MAT 206")]})

        response = upload(client, session_id, b"img", "t.png", "image/png")

        left = settings.AI_RATE_LIMIT_PER_HOUR - 1
        assert response.headers["x-ai-remaining-hour"] == str(left)
        assert response.headers["x-ai-limit-hour"] == str(settings.AI_RATE_LIMIT_PER_HOUR)
        assert client.get("/api/usage").json()["hour"]["remaining"] == left

    def test_failed_ai_calls_still_count(self, client, session_id, groq_like):
        upload(client, session_id, b"img", "t.png", "image/png")  # provider has no reply

        assert client.get("/api/usage").json()["hour"]["remaining"] == (
            settings.AI_RATE_LIMIT_PER_HOUR - 1
        )

    def test_daily_cap_blocks_uploads(self, client, session_id, groq_like, monkeypatch):
        monkeypatch.setattr(limits._daily_limiter, "max_requests", 1)
        groq_like.queue({"courses": [course("MAT 206")]})
        assert upload(client, session_id, b"img", "t.png", "image/png").status_code == 200

        blocked = upload(client, session_id, b"img", "t.png", "image/png")

        assert blocked.status_code == 429
        assert "AI limit for today" in blocked.json()["detail"]
        assert int(blocked.headers["retry-after"]) > 0
        assert client.get("/api/usage").json()["day"]["remaining"] == 0

    def test_rejected_files_do_not_use_quota(self, client, session_id, groq_like):
        response = upload(client, session_id, b"hello", "notes.txt", "text/plain")

        assert response.status_code == 400
        usage = client.get("/api/usage").json()
        assert usage["hour"]["remaining"] == settings.AI_RATE_LIMIT_PER_HOUR
        assert usage["day"]["remaining"] == settings.AI_DAILY_LIMIT
