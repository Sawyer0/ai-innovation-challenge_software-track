"""Sort provider failures into what a visitor can act on.

The raw provider error is logged server-side; the visitor gets a short message that
says whether to wait, retry, or upload something different.
"""

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx

FailureKind = Literal["busy", "timeout", "bad_reply", "error"]

DEFAULT_BUSY_RETRY_SECONDS = 30


@dataclass(frozen=True)
class ProviderFailure:
    kind: FailureKind
    retry_after: int | None = None


def _status_code(error: Exception) -> int | None:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code
    # anthropic.APIStatusError exposes status_code; google-genai APIError exposes code.
    for attr in ("status_code", "code"):
        value = getattr(error, attr, None)
        if isinstance(value, int):
            return value
    return None


def _retry_after(error: Exception) -> int | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("retry-after")
    try:
        return max(1, int(float(raw))) if raw is not None else None
    except ValueError:
        return None


def classify_provider_error(error: Exception) -> ProviderFailure:
    """Map an exception raised while calling a provider to a ProviderFailure."""
    if isinstance(error, httpx.TimeoutException | asyncio.TimeoutError | TimeoutError):
        return ProviderFailure("timeout")
    if "timeout" in type(error).__name__.lower():  # anthropic.APITimeoutError
        return ProviderFailure("timeout")
    status = _status_code(error)
    if status == 429 or (status is not None and status >= 500):
        return ProviderFailure("busy", _retry_after(error) or DEFAULT_BUSY_RETRY_SECONDS)
    if isinstance(error, ValueError):  # unparseable JSON reply
        return ProviderFailure("bad_reply")
    return ProviderFailure("error")


def busy_message(retry_after: int) -> str:
    return f"The demo is busy right now. Please try again in {retry_after} seconds."


TIMEOUT_MESSAGE = "The AI took too long to respond. Please try again in a moment."
