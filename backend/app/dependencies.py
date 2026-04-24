from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Annotated

from .database import get_db
from .exceptions import SessionNotFoundError, CourseNotFoundError, ProgramNotFoundError
from .repositories.session_repository import SessionRepository
from .repositories.course_repository import CourseRepository
from .repositories.program_repository import ProgramRepository
from .models import StudentSession, Course, Program

def get_session_repository(db: Session = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)

def get_course_repository(db: Session = Depends(get_db)) -> CourseRepository:
    return CourseRepository(db)

def get_program_repository(db: Session = Depends(get_db)) -> ProgramRepository:
    return ProgramRepository(db)

def get_current_session(
    session_id: str,
    repo: SessionRepository = Depends(get_session_repository)
) -> StudentSession:
    session = repo.get_by_session_id(session_id)
    if not session:
        raise SessionNotFoundError()
    return session

def get_current_course(
    course_code: str,
    repo: CourseRepository = Depends(get_course_repository)
) -> Course:
    course = repo.get_by_code(course_code)
    if not course:
        raise CourseNotFoundError()
    return course

def get_current_program(
    program_code: str,
    repo: ProgramRepository = Depends(get_program_repository)
) -> Program:
    program = repo.get_by_code(program_code)
    if not program:
        raise ProgramNotFoundError()
    return program

from .services.session_service import SessionService
from .services.course_service import CourseService
from .services.program_service import ProgramService
from .services.parser_service import ParserService

def get_session_service(repo: SessionRepository = Depends(get_session_repository)) -> SessionService:
    return SessionService(repo)

def get_course_service(repo: CourseRepository = Depends(get_course_repository)) -> CourseService:
    return CourseService(repo)

def get_program_service(repo: ProgramRepository = Depends(get_program_repository)) -> ProgramService:
    return ProgramService(repo)

def get_parser_service(session_service: SessionService = Depends(get_session_service)) -> ParserService:
    return ParserService(session_service)

from .services.prerequisite_service import PrerequisiteService
from .services.ai_service import AIService

def get_prerequisite_service(
    program_repo: ProgramRepository = Depends(get_program_repository),
    course_repo: CourseRepository = Depends(get_course_repository)
) -> PrerequisiteService:
    return PrerequisiteService(program_repo, course_repo)

def get_ai_service() -> AIService:
    return AIService()
