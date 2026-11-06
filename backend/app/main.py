"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import engine
from .infrastructure.ai import MISSING_KEY_MESSAGE
from .routers import advisement, courses, programs, sessions, transcript, usage
from .services.catalog_loader import initialize_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    if not settings.has_any_ai_key:
        logger.warning(MISSING_KEY_MESSAGE)
    yield


# In production the API shares an origin with the frontend and only /api/* reaches it,
# so the interactive docs move under /api as well.
_DOCS_PREFIX = "/api" if settings.APP_ENV == "production" else ""

app = FastAPI(
    title="Project DJA API",
    lifespan=lifespan,
    docs_url=f"{_DOCS_PREFIX}/docs",
    redoc_url=f"{_DOCS_PREFIX}/redoc",
    openapi_url=f"{_DOCS_PREFIX}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Let a cross-origin frontend (local dev) read the quota and retry headers.
    expose_headers=["Retry-After"]
    + [
        f"X-AI-{kind}-{window}"
        for kind in ("Limit", "Remaining", "Reset")
        for window in ("Minute", "Hour", "Day")
    ],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Project DJA API"}


@app.get("/health")
@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Report database connectivity and which AI providers have a key configured."""
    status: dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "database": "unknown",
        "ai_providers": {
            "claude": settings.has_anthropic_key,
            "gemini": settings.has_gemini_key,
            "groq": settings.has_groq_key,
        },
    }

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["database"] = "connected"
    except Exception as e:
        status["database"] = f"error: {e}"
        status["status"] = "degraded"

    if not settings.has_any_ai_key:
        status["status"] = "degraded"
        status["ai_error"] = MISSING_KEY_MESSAGE

    return status


app.include_router(courses.router)
app.include_router(programs.router)
app.include_router(sessions.router)
app.include_router(transcript.router)
app.include_router(advisement.router)
app.include_router(usage.router)
