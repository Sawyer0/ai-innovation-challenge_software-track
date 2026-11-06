from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Request, Response

from ..dependencies.rate_limit import ai_usage, client_ip, usage_headers

router = APIRouter(prefix="/api", tags=["usage"])


@router.get("/usage")
def get_usage(request: Request, response: Response) -> dict[str, Any]:
    """The caller's remaining AI quota. Free: not rate limited and doesn't count a request.

    ``minute`` and ``hour`` are per client IP; ``day`` is the demo-wide daily cap.
    Limits are kept in memory per server instance, so they are best-effort.
    """
    usage = ai_usage(client_ip(request))
    response.headers.update(usage_headers(usage))
    response.headers["Cache-Control"] = "no-store"
    return {name: asdict(window) for name, window in usage.items()} | {
        "scope": {"minute": "client", "hour": "client", "day": "global"},
    }
