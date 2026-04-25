"""
File type detection and routing for unified upload endpoint.
"""

import re
from typing import Dict, Any, Callable
from fastapi import UploadFile


async def detect_and_parse(file: UploadFile) -> Dict[str, Any]:
    """
    Auto-detect file type and route to appropriate parser.
    
    Supports:
    - CSV: Direct transcript parsing
    - PDF: Detects DegreeWorks vs CUNYfirst transcript
    - Images: Transcript parsing via Vision
    
    Args:
        file: UploadFile from FastAPI
        
    Returns:
        Parsed data in common format
        
    Raises:
        ValueError: If file type unsupported or detection fails
    """
    mime_type = file.content_type or ""
    filename = file.filename or ""
    
    # CSV files
    if mime_type == "text/csv" or filename.endswith(".csv"):
        from .transcript_parser import parse_transcript_csv
        return await parse_transcript_csv(file)
    
    # PDF files
    if mime_type == "application/pdf" or filename.endswith(".pdf"):
        # Peek at first 1000 chars of text to detect type
        preview = await _extract_pdf_text_preview(file)
        
        # DegreeWorks detection
        if "Degree Works" in preview or "Ellucian" in preview:
            from .degreeworks_parser import parse_degreeworks
            return await parse_degreeworks(file)
        else:
            # Assume CUNYfirst transcript
            from .transcript_parser import parse_transcript
            return await parse_transcript(file)
    
    # Images
    if mime_type.startswith("image/"):
        from .transcript_parser import parse_transcript
        return await parse_transcript(file)
    
    raise ValueError(f"Unsupported file type: {mime_type}")


async def _extract_pdf_text_preview(file: UploadFile, max_chars: int = 1000) -> str:
    """
    Extract text preview from PDF for type detection.
    
    Args:
        file: UploadFile
        max_chars: Maximum characters to extract
        
    Returns:
        Text preview from first page
    """
    try:
        # Try PyPDF2 first (optional dependency)
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            # PyPDF2 not installed - let AI parser handle detection
            return ""
        
        import io
        
        content = await file.read()
        await file.seek(0)
        
        reader = PdfReader(io.BytesIO(content))
        
        if len(reader.pages) > 0:
            text = reader.pages[0].extract_text() or ""
            return text[:max_chars]
        
        return ""
        
    except Exception:
        # Fallback: return empty, let parser handle it
        return ""


def get_parser_for_file(file: UploadFile) -> Callable:
    """
    Get the appropriate parser function for a file type.
    
    Returns:
        Parser function without calling it
    """
    mime_type = file.content_type or ""
    filename = file.filename or ""
    
    if mime_type == "text/csv" or filename.endswith(".csv"):
        from .transcript_parser import parse_transcript_csv
        return parse_transcript_csv
    
    if mime_type == "application/pdf" or filename.endswith(".pdf"):
        return None  # Need to peek content first
    
    if mime_type.startswith("image/"):
        from .transcript_parser import parse_transcript
        return parse_transcript
    
    raise ValueError(f"Unsupported file type: {mime_type}")
