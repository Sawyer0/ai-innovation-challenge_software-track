"""
Rate limiting dependency for FastAPI endpoints.
"""

import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response

from ..config import settings


@dataclass(frozen=True)
class WindowStatus:
    """Where one client stands in one window, as reported to the visitor."""

    limit: int
    remaining: int
    reset_seconds: int  # until the oldest counted request leaves the window; 0 if none


class RateLimiter:
    """Sliding window rate limiter keyed by session, IP, or a fixed global key."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # In-memory: on serverless each warm instance keeps its own window.
        self._requests: dict[str, list[float]] = {}

    def _prune(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        recent = [ts for ts in self._requests.get(key, []) if ts > cutoff]
        self._requests[key] = recent
        return recent

    def status(self, key: str) -> WindowStatus:
        """Report the key's window without counting a request."""
        now = time.time()
        recent = self._prune(key, now)
        reset = int(min(recent) + self.window_seconds - now) + 1 if recent else 0
        return WindowStatus(
            limit=self.max_requests,
            remaining=max(0, self.max_requests - len(recent)),
            reset_seconds=reset,
        )

    def record(self, key: str) -> None:
        self._prune(key, time.time()).append(time.time())

    def release(self, key: str) -> None:
        """Un-count the key's most recent request (it never reached the AI)."""
        recent = self._requests.get(key)
        if recent:
            recent.pop()

    def is_allowed(self, session_id: str) -> tuple:
        """
        Check if request is allowed for session, counting it when it is.

        Returns:
            Tuple of (allowed: bool, retry_after: Optional[int])
        """
        status = self.status(session_id)
        if status.remaining > 0:
            self.record(session_id)
            return True, None
        return False, status.reset_seconds

    def reset(self, session_id: str):
        """Reset rate limit for a session."""
        self._requests.pop(session_id, None)


# Default rate limiter: 10 requests per minute
_default_limiter = RateLimiter(max_requests=10, window_seconds=60)


async def rate_limit(request: Request, session_id: str | None = None) -> None:
    """
    FastAPI dependency for rate limiting.

    Usage:
        @router.post("/advisement")
        async def get_advisement(
            request: Request,
            _: None = Depends(rate_limit)
        ):
            pass
    """
    # Extract session_id from path params or query
    sid = session_id or request.path_params.get("session_id") or request.path_params.get("id")

    if not sid:
        # No session = no rate limiting (or use IP)
        return

    allowed, retry_after = _default_limiter.is_allowed(sid)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


# Per-IP limits for endpoints that spend LLM quota. Sessions are free to create, so a
# per-session limit alone doesn't stop one client from burning the provider quota.
# A global daily cap bounds total spend on the paid provider key.
#
# All three are in-memory, so on serverless each warm instance keeps its own windows:
# they are best-effort, and a visitor routed to a fresh instance starts a new count.
_minute_limiter = RateLimiter(max_requests=settings.AI_RATE_LIMIT_PER_MINUTE, window_seconds=60)
_hour_limiter = RateLimiter(max_requests=settings.AI_RATE_LIMIT_PER_HOUR, window_seconds=3600)
_daily_limiter = RateLimiter(max_requests=settings.AI_DAILY_LIMIT, window_seconds=86400)
_ai_ip_limiters = (_minute_limiter, _hour_limiter)
_GLOBAL_KEY = "*"


def client_ip(request: Request) -> str:
    """Best-effort client IP; proxy headers are trusted only when configured."""
    if settings.TRUST_PROXY_HEADERS:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def ai_usage(ip: str) -> dict[str, WindowStatus]:
    """The visitor's AI quota: per-IP minute and hour windows, and the global daily cap."""
    return {
        "minute": _minute_limiter.status(ip),
        "hour": _hour_limiter.status(ip),
        "day": _daily_limiter.status(_GLOBAL_KEY),
    }


def usage_headers(usage: dict[str, WindowStatus]) -> dict[str, str]:
    """X-AI-* headers so the frontend can show the remaining quota after each call."""
    headers: dict[str, str] = {}
    for name, window in usage.items():
        label = name.capitalize()
        headers[f"X-AI-Limit-{label}"] = str(window.limit)
        headers[f"X-AI-Remaining-{label}"] = str(window.remaining)
        headers[f"X-AI-Reset-{label}"] = str(window.reset_seconds)
    return headers


def _wait(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} seconds"
    if seconds < 5400:
        return f"{round(seconds / 60)} minutes"
    return f"{round(seconds / 3600)} hours"


async def ai_rate_limit(request: Request, response: Response) -> None:
    """FastAPI dependency: per-IP minute/hour limits and a global daily cap on LLM endpoints.

    Allowed requests are counted against all three windows and get X-AI-* headers.
    """
    ip = client_ip(request)
    usage = ai_usage(ip)
    day, hour, minute = usage["day"], usage["hour"], usage["minute"]

    message = None
    if day.remaining == 0:
        retry_after = day.reset_seconds
        message = (
            "The demo has reached its AI limit for today. "
            f"Please try again in about {_wait(retry_after)}."
        )
    elif hour.remaining == 0:
        retry_after = hour.reset_seconds
        message = (
            f"You've used all {hour.limit} AI requests for this hour. "
            f"Please try again in about {_wait(retry_after)}."
        )
    elif minute.remaining == 0:
        retry_after = minute.reset_seconds
        message = f"Too many AI requests at once. Please try again in {_wait(retry_after)}."
    if message is not None:
        raise HTTPException(
            status_code=429,
            detail=message,
            headers={"Retry-After": str(retry_after), **usage_headers(usage)},
        )

    for limiter in _ai_ip_limiters:
        limiter.record(ip)
    _daily_limiter.record(_GLOBAL_KEY)
    response.headers.update(usage_headers(ai_usage(ip)))


def release_ai_request(request: Request) -> None:
    """Give back the quota an AI endpoint counted when it rejected the input before
    calling a provider (unsupported or locked file)."""
    ip = client_ip(request)
    for limiter in _ai_ip_limiters:
        limiter.release(ip)
    _daily_limiter.release(_GLOBAL_KEY)


def reset_ai_rate_limits() -> None:
    """Clear the AI limits (used by tests)."""
    for limiter in (*_ai_ip_limiters, _daily_limiter):
        limiter._requests.clear()


def get_rate_limiter(max_requests: int = 10, window_seconds: int = 60) -> RateLimiter:
    """Get a custom rate limiter instance."""
    return RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
