"""Per-IP rate limiting on the LLM-backed endpoints."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.config import settings
from app.dependencies.rate_limit import ai_rate_limit, client_ip

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
        await ai_rate_limit(req)  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as exc:
        await ai_rate_limit(req)  # type: ignore[arg-type]
    assert exc.value.status_code == 429
    assert exc.value.headers and "Retry-After" in exc.value.headers

    # A different client is unaffected.
    await ai_rate_limit(_request(host="203.0.113.8"))  # type: ignore[arg-type]
