from sqlalchemy.orm import Session
from typing import List
from ..models import Program
from .base import BaseRepository


class ProgramRepository(BaseRepository[Program]):
    """Repository for Program entity operations."""

    def __init__(self, db: Session):
        super().__init__(db, Program)

    def get_by_code(self, code: str) -> Program:
        """Get program by its program code."""
        return self.get_by_field("program_code", code)

    def list_paginated(self, skip: int = 0, limit: int = 100) -> List[Program]:
        """List all programs with pagination."""
        return self.list_all(skip, limit)
