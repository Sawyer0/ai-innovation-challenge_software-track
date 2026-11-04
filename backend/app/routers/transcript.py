from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..dependencies import get_current_session, get_parser_service
from ..models import StudentSession
from ..parsers.transcript_parser import TranscriptParsingError
from ..services.parser_service import ParserService

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("/{session_id}/transcript")
async def upload_transcript(
    file: UploadFile = File(...),
    session: StudentSession = Depends(get_current_session),
    parser_service: ParserService = Depends(get_parser_service),
):
    """Parse an uploaded transcript (PDF or image) into {profile, courses} for review."""
    try:
        return await parser_service.parse_and_save(file, session.session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TranscriptParsingError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
