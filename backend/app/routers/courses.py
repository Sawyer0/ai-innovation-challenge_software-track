from fastapi import APIRouter, Depends, Query

from .. import models, schemas
from ..dependencies import get_course_service, get_current_course
from ..services.course_service import CourseService

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("/", response_model=list[schemas.Course])
def read_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = None,
    service: CourseService = Depends(get_course_service),
):
    return service.list_courses(skip, limit, search)


@router.get("/{course_code}", response_model=schemas.CourseDetail)
def read_course(course: models.Course = Depends(get_current_course)):
    return course
