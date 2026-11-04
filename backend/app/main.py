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
from .routers import advisement, courses, programs, sessions, transcript, upload
from .services.catalog_loader import initialize_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    if not settings.has_any_ai_key:
        logger.warning(MISSING_KEY_MESSAGE)
    yield


app = FastAPI(title="Project DJA API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Project DJA API"}


@app.get("/health")
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
app.include_router(upload.router)
app.include_router(transcript.router)
app.include_router(advisement.router)
