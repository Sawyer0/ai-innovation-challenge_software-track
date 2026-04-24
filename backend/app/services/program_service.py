from typing import List, Optional
from ..models import Program
from ..repositories.program_repository import ProgramRepository

class ProgramService:
    def __init__(self, repo: ProgramRepository):
        self.repo = repo

    def get_program(self, code: str) -> Optional[Program]:
        return self.repo.get_by_code(code)

    def list_programs(self, skip: int = 0, limit: int = 100) -> List[Program]:
        return self.repo.list_paginated(skip, limit)
