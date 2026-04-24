from fastapi import HTTPException

class AppException(HTTPException):
    def __init__(self, detail: str = "An error occurred", status_code: int = 500):
        super().__init__(status_code=status_code, detail=detail)

class SessionNotFoundError(AppException):
    def __init__(self, detail: str = "Session not found"):
        super().__init__(detail=detail, status_code=404)

class CourseNotFoundError(AppException):
    def __init__(self, detail: str = "Course not found"):
        super().__init__(detail=detail, status_code=404)

class ProgramNotFoundError(AppException):
    def __init__(self, detail: str = "Program not found"):
        super().__init__(detail=detail, status_code=404)
