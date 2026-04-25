"""
Unified upload endpoint supporting DegreeWorks PDFs, CUNYfirst transcripts, and CSV.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from ..models import StudentSession
from ..dependencies import get_current_session, get_parser_service
from ..dependencies.rate_limit import rate_limit
from ..services.parser_service import ParserService

router = APIRouter(prefix="/api/session", tags=["upload"])


class ConfirmUploadRequest(BaseModel):
    """Request body for confirming upload."""
    courses: List[Dict[str, Any]]


@router.post("/{session_id}/upload")
async def upload_file(
    file: UploadFile = File(...),
    session: StudentSession = Depends(get_current_session),
    parser_service: ParserService = Depends(get_parser_service)
):
    """
    Unified upload endpoint with auto-detection.
    
    Supports:
    - DegreeWorks PDFs (auto-detected via "Degree Works" / "Ellucian" text)
    - CUNYfirst transcripts (image, PDF)
    - CSV files
    
    Returns parsed data for review. Use POST /upload/confirm to save.
    """
    try:
        result = await parser_service.parse_and_save(
            file=file,
            session_id=session.session_id,
            confirm=False  # Preview only
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")


@router.post("/{session_id}/upload/confirm")
async def confirm_upload(
    request: ConfirmUploadRequest,
    session: StudentSession = Depends(get_current_session),
    parser_service: ParserService = Depends(get_parser_service)
):
    """
    Confirm and save courses from previous upload.
    
    Accepts the courses array from the /upload response and saves to session.
    """
    try:
        result = await parser_service.confirm_and_save(
            courses=request.courses,
            session_id=session.session_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save courses: {e}")


# Deprecated: Keep for backward compatibility, redirects to new endpoint
@router.post("/{session_id}/transcript")
async def upload_transcript_legacy(
    file: UploadFile = File(...),
    session: StudentSession = Depends(get_current_session),
    parser_service: ParserService = Depends(get_parser_service)
):
    """
    [DEPRECATED] Use POST /{session_id}/upload instead.
    
    Redirects to unified upload endpoint.
    """
    try:
        result = await parser_service.parse_and_save(
            file=file,
            session_id=session.session_id,
            confirm=True  # Legacy behavior: auto-save
        )
        return {
            "message": f"Successfully parsed {result.get('saved_count', 0)} courses",
            "courses": result.get("all_courses", []),
            "note": "This endpoint is deprecated. Use POST /{session_id}/upload"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/transcript/confirm")
async def confirm_transcript_legacy(
    request: ConfirmUploadRequest,
    session: StudentSession = Depends(get_current_session),
    parser_service: ParserService = Depends(get_parser_service)
):
    """
    [DEPRECATED] Use POST /{session_id}/upload/confirm instead.
    
    Legacy confirmation endpoint - redirects to new endpoint.
    """
    try:
        result = await parser_service.confirm_and_save(
            courses=request.courses,
            session_id=session.session_id
        )
        return {
            **result,
            "note": "This endpoint is deprecated. Use POST /{session_id}/upload/confirm"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save courses: {e}")
