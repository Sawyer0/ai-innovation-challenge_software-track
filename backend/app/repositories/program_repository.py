from sqlalchemy.orm import Session
from typing import List
from ..models import Program
from .base import BaseRepository

class ProgramRepository(BaseRepository):
    def get_by_code(self, code: str) -> Program:
        return self.db.query(Program).filter(Program.program_code == code).first()

    def list_paginated(self, skip: int = 0, limit: int = 100) -> List[Program]:
        return self.db.query(Program).offset(skip).limit(limit).all()
