from fastapi import APIRouter, Depends, Query

from .. import models, schemas
from ..dependencies import get_current_program, get_program_service
from ..services.program_service import ProgramService

router = APIRouter(prefix="/api/programs", tags=["programs"])


@router.get("/", response_model=list[schemas.Program])
def read_programs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: ProgramService = Depends(get_program_service),
):
    return service.list_programs(skip, limit)


@router.get("/{program_code}", response_model=schemas.Program)
def read_program(program: models.Program = Depends(get_current_program)):
    return program
