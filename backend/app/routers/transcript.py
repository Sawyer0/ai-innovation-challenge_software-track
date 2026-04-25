from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from ..models import StudentSession
from ..dependencies import get_current_session, get_parser_service
from ..services.parser_service import ParserService

router = APIRouter(prefix="/api/session", tags=["session"])

@router.post("/{session_id}/transcript")
async def upload_transcript(
    file: UploadFile = File(...),
    session: StudentSession = Depends(get_current_session),
    parser_service: ParserService = Depends(get_parser_service)
):
    try:
        result = await parser_service.parse_and_save(file, session.session_id)
        return result  # {profile: {...}, courses: [...]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
