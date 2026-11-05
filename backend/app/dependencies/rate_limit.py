"""
Rate limiting dependency for FastAPI endpoints.
"""

import time

from fastapi import HTTPException, Request

from ..config import settings


class RateLimiter:
    """Sliding window rate limiter per session."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # In production, use Redis. For now, in-memory with session scope.
        self._requests: dict[str, list] = {}

    def is_allowed(self, session_id: str) -> tuple:
        """
        Check if request is allowed for session.

        Returns:
            Tuple of (allowed: bool, retry_after: Optional[int])
        """
        now = time.time()

        if session_id not in self._requests:
            self._requests[session_id] = []

        # Clean old requests outside window
        cutoff = now - self.window_seconds
        self._requests[session_id] = [ts for ts in self._requests[session_id] if ts > cutoff]

        # Check if under limit
        if len(self._requests[session_id]) < self.max_requests:
            self._requests[session_id].append(now)
            return True, None

        # Rate limited - calculate retry after
        oldest = min(self._requests[session_id])
        retry_after = int(oldest + self.window_seconds - now) + 1
        return False, retry_after

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
# In-memory, so on serverless each warm instance keeps its own window.
_ai_ip_limiters = (
    RateLimiter(max_requests=settings.AI_RATE_LIMIT_PER_MINUTE, window_seconds=60),
    RateLimiter(max_requests=settings.AI_RATE_LIMIT_PER_HOUR, window_seconds=3600),
)


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


async def ai_rate_limit(request: Request) -> None:
    """FastAPI dependency: per-IP minute and hour limits on LLM-backed endpoints."""
    ip = client_ip(request)
    for limiter in _ai_ip_limiters:
        allowed, retry_after = limiter.is_allowed(ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many AI requests from this address. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


def reset_ai_rate_limits() -> None:
    """Clear the per-IP AI limits (used by tests)."""
    for limiter in _ai_ip_limiters:
        limiter._requests.clear()


def get_rate_limiter(max_requests: int = 10, window_seconds: int = 60) -> RateLimiter:
    """Get a custom rate limiter instance."""
    return RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
