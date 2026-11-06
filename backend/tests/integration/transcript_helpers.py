"""Helpers for transcript upload tests (fixtures live in conftest.py)."""

import io
from typing import Any


def course(code: str, **fields: Any) -> dict[str, Any]:
    """A course row as a provider would return it."""
    return {
        "course_code": code,
        "course_title": code,
        "semester_taken": "Fall 2025",
        "credits": 3,
        "grade": "A",
        "status": "completed",
    } | fields


def upload(client, session_id: str, data: bytes, name="Transcript.pdf", mime="application/pdf"):
    return client.post(
        f"/api/session/{session_id}/transcript", files={"file": (name, io.BytesIO(data), mime)}
    )
