from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..dependencies import get_parser_service, require_session_id
from ..dependencies.rate_limit import ai_rate_limit, release_ai_request
from ..infrastructure.ai import NoProviderConfiguredError
from ..parsers.transcript_parser import TranscriptParsingError
from ..services.parser_service import ParserService

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("/{session_id}/transcript")
async def upload_transcript(
    request: Request,
    file: UploadFile = File(...),
    # Parsing keeps no session state, so it works on any instance (sessions are per
    # instance on Vercel); the id only has to be well formed.
    _session_id: str = Depends(require_session_id),
    parser_service: ParserService = Depends(get_parser_service),
    _: None = Depends(ai_rate_limit),
):
    """Parse an uploaded transcript (PDF or image) into {profile, courses} for review."""
    try:
        return await parser_service.parse(file)
    except NoProviderConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        # Rejected before any AI call (unsupported or locked file): don't count it.
        release_ai_request(request)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TranscriptParsingError as e:
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
        raise HTTPException(status_code=e.status_code, detail=str(e), headers=headers) from e
