"""
Dependency injection utilities for FastAPI.

Provides factory functions for repositories, services, and entity lookups.
Uses generic factories to reduce boilerplate code.
"""

import uuid
from collections.abc import Callable
from typing import TypeVar

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import CourseNotFoundError, ProgramNotFoundError, SessionNotFoundError
from ..models import Course, Program, StudentSession
from ..repositories.base import BaseRepository
from ..repositories.course_repository import CourseRepository
from ..repositories.program_repository import ProgramRepository
from ..repositories.session_repository import SessionRepository
from ..services.ai_service import AIService
from ..services.cleanup_service import CleanupService
from ..services.course_service import CourseService
from ..services.parser_service import ParserService
from ..services.prerequisite_service import PrerequisiteService
from ..services.program_service import ProgramService
from ..services.session_service import SessionService
from .rate_limit import RateLimiter, get_rate_limiter, rate_limit

R = TypeVar("R", bound=BaseRepository)


def get_repository(repo_class: Callable[[Session], R]) -> Callable[[Session], R]:
    """
    Create a factory function for a repository class.

    Args:
        repo_class: Repository class to instantiate

    Returns:
        Factory function that takes a DB session and returns repository instance

    Example:
        get_course_repo = get_repository(CourseRepository)
        # Usage in endpoint:
        # course_repo: CourseRepository = Depends(get_course_repo)
    """

    def factory(db: Session = Depends(get_db)) -> R:
        return repo_class(db)

    return factory


# Repository dependency factories
get_session_repository = get_repository(SessionRepository)
get_course_repository = get_repository(CourseRepository)
get_program_repository = get_repository(ProgramRepository)


def get_current_session(
    session_id: str, repo: SessionRepository = Depends(get_session_repository)
) -> StudentSession:
    """Get current student session by ID or raise 404."""
    session = repo.get_by_session_id(session_id)
    if not session:
        raise SessionNotFoundError()
    return session


def is_session_id(session_id: str) -> bool:
    """True for ids shaped like the ones POST /api/session hands out (UUIDs)."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        return False
    return True


def get_or_create_session(
    session_id: str, repo: SessionRepository = Depends(get_session_repository)
) -> StudentSession:
    """Get the session, recreating it when this server instance has never seen it.

    Sessions live in a per-instance SQLite file on Vercel, so a valid id the browser
    holds can reach an instance (or a fresh deploy) without its row. Treat that as a
    new, empty session instead of failing; ids that aren't UUIDs still get a 404.
    """
    if not is_session_id(session_id):
        raise SessionNotFoundError()
    session = repo.get_by_session_id(session_id)
    if session is not None:
        return session
    try:
        return repo.create_session(session_id)
    except IntegrityError:
        # A concurrent request on this instance created it first.
        repo.db.rollback()
        session = repo.get_by_session_id(session_id)
        if session is None:
            raise
        return session


def require_session_id(session_id: str) -> str:
    """Check the id's shape only, for endpoints that keep no per-session state."""
    if not is_session_id(session_id):
        raise SessionNotFoundError()
    return session_id


def get_current_course(
    course_code: str, repo: CourseRepository = Depends(get_course_repository)
) -> Course:
    """Get current course by code or raise 404."""
    course = repo.get_by_code(course_code)
    if not course:
        raise CourseNotFoundError()
    return course


def get_current_program(
    program_code: str, repo: ProgramRepository = Depends(get_program_repository)
) -> Program:
    """Get current program by code or raise 404."""
    program = repo.get_by_code(program_code)
    if not program:
        raise ProgramNotFoundError()
    return program


def get_session_service(
    repo: SessionRepository = Depends(get_session_repository),
) -> SessionService:
    """Get SessionService instance."""
    return SessionService(repo)


def get_course_service(repo: CourseRepository = Depends(get_course_repository)) -> CourseService:
    """Get CourseService instance."""
    return CourseService(repo)


def get_program_service(
    repo: ProgramRepository = Depends(get_program_repository),
) -> ProgramService:
    """Get ProgramService instance."""
    return ProgramService(repo)


def get_parser_service(
    session_service: SessionService = Depends(get_session_service),
) -> ParserService:
    """Get ParserService instance."""
    return ParserService(session_service)


def get_prerequisite_service(
    program_repo: ProgramRepository = Depends(get_program_repository),
    course_repo: CourseRepository = Depends(get_course_repository),
) -> PrerequisiteService:
    """Get PrerequisiteService instance."""
    return PrerequisiteService(program_repo, course_repo)


def get_ai_service() -> AIService:
    """Get AIService instance (no dependencies)."""
    return AIService()


def get_cleanup_service(db: Session = Depends(get_db)) -> CleanupService:
    """Get CleanupService instance."""
    return CleanupService(db)


__all__ = [
    "RateLimiter",
    "get_ai_service",
    "get_cleanup_service",
    "get_course_repository",
    "get_course_service",
    "get_current_course",
    "get_current_program",
    "get_current_session",
    "get_or_create_session",
    "get_parser_service",
    "get_prerequisite_service",
    "get_program_repository",
    "get_program_service",
    "get_rate_limiter",
    "get_repository",
    "get_session_repository",
    "get_session_service",
    "is_session_id",
    "rate_limit",
    "require_session_id",
]
