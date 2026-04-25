"""
DegreeWorks PDF parser using Gemini Vision.
"""

from typing import Dict, Any, List
from fastapi import UploadFile
from ..prompts import DEGREEWORKS_SYSTEM_PROMPT, DEGREEWORKS_USER_PROMPT
from ..infrastructure.ai import get_ai_client, AIError
from ..utils.ai_helpers import safe_json_parse
from ..parsers.validators import (
    validate_course_codes,
    deduplicate_courses,
    normalize_course_code,
    flag_low_confidence_courses
)


class DegreeWorksParser:
    """Parser for DegreeWorks audit PDFs."""
    
    def __init__(self):
        self.ai_client = get_ai_client()
    
    async def parse(self, file: UploadFile) -> Dict[str, Any]:
        """
        Parse a DegreeWorks PDF and return structured data.
        
        Args:
            file: UploadFile containing PDF data
            
        Returns:
            Dict with confidence, student, courses, requirements
        """
        file_content = await file.read()
        await file.seek(0)
        
        mime_type = file.content_type or "application/pdf"
        
        try:
            response_text = self.ai_client.generate_content(
                contents=[
                    DEGREEWORKS_SYSTEM_PROMPT,
                    {"mime_type": mime_type, "data": file_content},
                    DEGREEWORKS_USER_PROMPT
                ]
            )
            
            # Parse JSON response
            parsed = safe_json_parse(response_text, default={})
            
            if not parsed:
                raise ValueError("Failed to parse DegreeWorks response")
            
            # Process and validate courses
            courses = parsed.get("courses", [])
            
            # Validate and normalize course codes
            valid_courses, invalid_courses = validate_course_codes(courses)
            
            # Deduplicate (handles Fall Through + In Progress duplicates)
            deduplicated = deduplicate_courses(valid_courses)
            
            # Flag low confidence items
            flagged = flag_low_confidence_courses(deduplicated, threshold=0.7)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_confidence(
                parsed.get("confidence", 0.0),
                deduplicated,
                len(invalid_courses)
            )
            
            return {
                "source": "degreeworks",
                "confidence": overall_confidence,
                "student": parsed.get("student", {}),
                "courses": {
                    "completed": [
                        c for c in deduplicated 
                        if c.get("status") in ["completed", "passed"]
                    ],
                    "in_progress": [
                        c for c in deduplicated 
                        if c.get("status") in ["in_progress", "enrolled"]
                    ],
                    "still_needed": [
                        c for c in deduplicated 
                        if c.get("status") in ["still_needed", "needed"]
                    ],
                    "fall_through": [
                        c for c in deduplicated 
                        if c.get("status") in ["fall_through", "not_met"]
                    ]
                },
                "all_courses": deduplicated,
                "requirements": parsed.get("requirements", []),
                "validated": deduplicated,
                "flagged": flagged,
                "invalid": invalid_courses,
                "requires_confirmation": len(flagged) > 0 or len(invalid_courses) > 0
            }
            
        except AIError as e:
            raise ValueError(f"AI parsing error: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse DegreeWorks PDF: {e}")
    
    def _calculate_confidence(
        self, 
        base_confidence: float, 
        courses: List[Dict], 
        invalid_count: int
    ) -> float:
        """Calculate overall confidence score."""
        if not courses:
            return base_confidence * 0.5  # Penalty for no courses
        
        # Average course confidence
        avg_course_conf = sum(
            c.get("confidence", 0.8) for c in courses
        ) / len(courses)
        
        # Penalty for invalid courses
        invalid_penalty = min(invalid_count * 0.05, 0.2)
        
        # Weighted combination
        overall = (base_confidence * 0.3) + (avg_course_conf * 0.7) - invalid_penalty
        return max(0.0, min(1.0, overall))


async def parse_degreeworks(file: UploadFile) -> Dict[str, Any]:
    """Convenience function to parse DegreeWorks PDF."""
    parser = DegreeWorksParser()
    return await parser.parse(file)
