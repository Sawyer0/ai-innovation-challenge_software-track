"""
Dependency injection utilities for FastAPI.

Provides factory functions for repositories, services, and entity lookups.
Uses generic factories to reduce boilerplate code.
"""

from typing import Type, TypeVar, Callable, Optional
from fastapi import Depends
from sqlalchemy.orm import Session

from .database import get_db
from .exceptions import SessionNotFoundError, CourseNotFoundError, ProgramNotFoundError
from .repositories.base import BaseRepository
from .repositories.session_repository import SessionRepository
from .repositories.course_repository import CourseRepository
from .repositories.program_repository import ProgramRepository
from .models import StudentSession, Course, Program

# Generic type for repositories
T = TypeVar("T")
R = TypeVar("R", bound=BaseRepository)


def get_repository(repo_class: Type[R]) -> Callable[[Session], R]:
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


# Generic entity lookup factory
def get_current_entity(
    repo: BaseRepository,
    lookup_method: str,
    param_value: str,
    not_found_error: Exception
):
    """Generic helper to fetch an entity or raise an error."""
    method = getattr(repo, lookup_method)
    entity = method(param_value)
    if not entity:
        raise not_found_error
    return entity


def get_current_session(
    session_id: str,
    repo: SessionRepository = Depends(get_session_repository)
) -> StudentSession:
    """Get current student session by ID or raise 404."""
    session = repo.get_by_session_id(session_id)
    if not session:
        raise SessionNotFoundError()
    return session


def get_current_course(
    course_code: str,
    repo: CourseRepository = Depends(get_course_repository)
) -> Course:
    """Get current course by code or raise 404."""
    course = repo.get_by_code(course_code)
    if not course:
        raise CourseNotFoundError()
    return course


def get_current_program(
    program_code: str,
    repo: ProgramRepository = Depends(get_program_repository)
) -> Program:
    """Get current program by code or raise 404."""
    program = repo.get_by_code(program_code)
    if not program:
        raise ProgramNotFoundError()
    return program


# Service imports and factories
from .services.session_service import SessionService
from .services.course_service import CourseService
from .services.program_service import ProgramService
from .services.parser_service import ParserService
from .services.prerequisite_service import PrerequisiteService
from .services.ai_service import AIService


def get_service(service_class: Type[T], *repo_deps: Callable) -> Callable[..., T]:
    """
    Create a factory function for a service class.

    Args:
        service_class: Service class to instantiate
        *repo_deps: Repository dependency factory functions

    Returns:
        Factory function for the service

    Example:
        get_course_service = get_service(CourseService, get_course_repository)
    """
    def factory(*repos):
        return service_class(*repos)
    factory.__signature__ = None  # Will be set by FastAPI Depends
    return lambda **deps: service_class(*[deps.get(f"repo_{i}") for i in range(len(repo_deps))])


def get_session_service(repo: SessionRepository = Depends(get_session_repository)) -> SessionService:
    """Get SessionService instance."""
    return SessionService(repo)


def get_course_service(repo: CourseRepository = Depends(get_course_repository)) -> CourseService:
    """Get CourseService instance."""
    return CourseService(repo)


def get_program_service(repo: ProgramRepository = Depends(get_program_repository)) -> ProgramService:
    """Get ProgramService instance."""
    return ProgramService(repo)


def get_parser_service(
    session_service: SessionService = Depends(get_session_service)
) -> ParserService:
    """Get ParserService instance."""
    return ParserService(session_service)


def get_prerequisite_service(
    program_repo: ProgramRepository = Depends(get_program_repository),
    course_repo: CourseRepository = Depends(get_course_repository)
) -> PrerequisiteService:
    """Get PrerequisiteService instance."""
    return PrerequisiteService(program_repo, course_repo)


def get_ai_service() -> AIService:
    """Get AIService instance (no dependencies)."""
    return AIService()
