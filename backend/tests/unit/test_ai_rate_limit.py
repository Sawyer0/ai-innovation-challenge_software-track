"""Per-IP rate limiting on the LLM-backed endpoints."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from app.config import settings
from app.dependencies.rate_limit import ai_rate_limit, client_ip

# The module, not the same-named dependency that app.dependencies re-exports.
limits = import_module("app.dependencies.rate_limit")

pytestmark = pytest.mark.unit


def _request(headers: dict[str, str] | None = None, host: str = "10.0.0.1"):
    return SimpleNamespace(headers=headers or {}, client=SimpleNamespace(host=host))


def test_client_ip_ignores_proxy_headers_by_default(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    req = _request({"x-forwarded-for": "1.2.3.4"})
    assert client_ip(req) == "10.0.0.1"  # type: ignore[arg-type]


def test_client_ip_reads_proxy_headers_when_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    assert client_ip(_request({"x-real-ip": "5.6.7.8"})) == "5.6.7.8"  # type: ignore[arg-type]
    req = _request({"x-forwarded-for": "1.2.3.4, 9.9.9.9"})
    assert client_ip(req) == "1.2.3.4"  # type: ignore[arg-type]


async def test_ai_rate_limit_blocks_after_per_minute_budget(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    req = _request(host="203.0.113.7")
    for _ in range(settings.AI_RATE_LIMIT_PER_MINUTE):
        await ai_rate_limit(req, Response())  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as exc:
        await ai_rate_limit(req, Response())  # type: ignore[arg-type]
    assert exc.value.status_code == 429
    assert exc.value.headers and "Retry-After" in exc.value.headers

    # A different client is unaffected.
    await ai_rate_limit(_request(host="203.0.113.8"), Response())  # type: ignore[arg-type]


async def test_allowed_requests_report_remaining_quota_in_headers(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    response = Response()

    await ai_rate_limit(_request(host="203.0.113.9"), response)  # type: ignore[arg-type]

    hour = settings.AI_RATE_LIMIT_PER_HOUR
    assert response.headers["X-AI-Limit-Hour"] == str(hour)
    assert response.headers["X-AI-Remaining-Hour"] == str(hour - 1)
    assert 3500 < int(response.headers["X-AI-Reset-Hour"]) <= 3601
    assert response.headers["X-AI-Remaining-Day"] == str(settings.AI_DAILY_LIMIT - 1)


async def test_hourly_limit_says_when_to_retry(monkeypatch):
    monkeypatch.setattr(limits._minute_limiter, "max_requests", 100)
    monkeypatch.setattr(limits._hour_limiter, "max_requests", 2)
    req = _request(host="203.0.113.10")
    for _ in range(2):
        await ai_rate_limit(req, Response())  # type: ignore[arg-type]

    with pytest.raises(HTTPException) as exc:
        await ai_rate_limit(req, Response())  # type: ignore[arg-type]

    assert exc.value.status_code == 429
    assert "all 2 AI requests for this hour" in exc.value.detail
    assert "60 minutes" in exc.value.detail
    assert exc.value.headers and exc.value.headers["X-AI-Remaining-Hour"] == "0"
    assert 3500 < int(exc.value.headers["Retry-After"]) <= 3601


async def test_global_daily_cap_applies_across_clients(monkeypatch):
    monkeypatch.setattr(limits._daily_limiter, "max_requests", 2)
    await ai_rate_limit(_request(host="198.51.100.1"), Response())  # type: ignore[arg-type]
    await ai_rate_limit(_request(host="198.51.100.2"), Response())  # type: ignore[arg-type]

    with pytest.raises(HTTPException) as exc:
        await ai_rate_limit(_request(host="198.51.100.3"), Response())  # type: ignore[arg-type]

    assert exc.value.status_code == 429
    assert "AI limit for today" in exc.value.detail
    assert exc.value.headers and int(exc.value.headers["Retry-After"]) > 86000


async def test_a_blocked_request_is_not_counted(monkeypatch):
    monkeypatch.setattr(limits._minute_limiter, "max_requests", 1)
    req = _request(host="203.0.113.11")
    await ai_rate_limit(req, Response())  # type: ignore[arg-type]
    with pytest.raises(HTTPException):
        await ai_rate_limit(req, Response())  # type: ignore[arg-type]

    assert limits._hour_limiter.status("203.0.113.11").remaining == (
        settings.AI_RATE_LIMIT_PER_HOUR - 1
    )
    assert limits._daily_limiter.status("*").remaining == settings.AI_DAILY_LIMIT - 1
