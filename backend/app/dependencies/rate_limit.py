"""
Rate limiting dependency for FastAPI endpoints.
"""

import time
from typing import Dict, Optional
from fastapi import Request, HTTPException, Depends
from ..repositories.session_repository import SessionRepository


class RateLimiter:
    """Sliding window rate limiter per session."""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # In production, use Redis. For now, in-memory with session scope.
        self._requests: Dict[str, list] = {}
    
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
        self._requests[session_id] = [
            ts for ts in self._requests[session_id] if ts > cutoff
        ]
        
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


async def rate_limit(
    request: Request,
    session_id: Optional[str] = None
) -> None:
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
            headers={"Retry-After": str(retry_after)}
        )


def get_rate_limiter(max_requests: int = 10, window_seconds: int = 60) -> RateLimiter:
    """Get a custom rate limiter instance."""
    return RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
