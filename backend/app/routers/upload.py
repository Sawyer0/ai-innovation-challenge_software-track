"""
Upload endpoint — parses transcripts and DegreeWorks files.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from ..models import StudentSession
from ..dependencies import get_current_session, get_parser_service
from ..services.parser_service import ParserService

router = APIRouter(prefix="/api/session", tags=["upload"])


@router.post("/{session_id}/upload")
async def upload_file(
    file: UploadFile = File(...),
    session: StudentSession = Depends(get_current_session),
    parser_service: ParserService = Depends(get_parser_service),
):
    """
    Parse an uploaded transcript or DegreeWorks file.
    Returns {profile, courses} for the frontend to display and prefill.
    """
    try:
        result = await parser_service.parse_and_save(
            file=file,
            session_id=session.session_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")
