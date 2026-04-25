"""
Course validation and deduplication utilities.
"""

import re
from typing import List, Dict, Any, Optional


def validate_course_code(code: str) -> bool:
    """
    Validate course code format (e.g., "MAT 157", "CSC201", "ENG-101").
    
    Args:
        code: Course code to validate
        
    Returns:
        True if valid course code format
    """
    if not code or not isinstance(code, str):
        return False
    
    # Pattern: 2-4 letters, optional space/dash/dot, 2-4 digits, optional .5
    pattern = r'^[A-Z]{2,4}[\s\-\.]?\d{2,4}(?:\.5)?$'
    return bool(re.match(pattern, code.upper().strip()))


def normalize_course_code(code: str) -> str:
    """
    Normalize course code to standard format (e.g., "MAT 157.5" -> "MAT157.5").
    
    Args:
        code: Raw course code
        
    Returns:
        Normalized course code (e.g., "MAT157.5")
    """
    if not code:
        return ""
    
    # Remove spaces, dashes, dots between subject and number
    code = code.upper().strip()
    # Pattern to extract subject letters and number
    match = re.match(r'^([A-Z]{2,4})[\s\-\.]?(\d{2,4}(?:\.5)?)$', code)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return code


def validate_course_codes(courses: List[Dict[str, Any]]) -> tuple:
    """
    Validate course codes in a list of course dictionaries.
    
    Args:
        courses: List of course dicts with 'code' key
        
    Returns:
        Tuple of (valid_courses, invalid_courses)
    """
    valid = []
    invalid = []
    
    for course in courses:
        code = course.get("code", "")
        if validate_course_code(code):
            course["code"] = normalize_course_code(code)
            valid.append(course)
        else:
            invalid.append(course)
    
    return valid, invalid


def deduplicate_courses(courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate courses keeping the highest priority entry.
    
    DegreeWorks shows same course in multiple sections (Fall Through, 
    In Progress, Split). Priority: in_progress > completed > still_needed > fall_through
    
    Args:
        courses: List of course dicts with 'code' and 'status' keys
        
    Returns:
        Deduplicated list of courses
    """
    seen: Dict[str, Dict[str, Any]] = {}
    priority = {
        "in_progress": 4,
        "enrolled": 4,
        "completed": 3,
        "passed": 3,
        "still_needed": 2,
        "needed": 2,
        "fall_through": 1,
        "not_met": 1,
    }
    
    for course in courses:
        code = normalize_course_code(course.get("code", ""))
        if not code:
            continue
            
        status = course.get("status", "").lower().replace(" ", "_")
        
        if code not in seen:
            seen[code] = course
        else:
            current_priority = priority.get(status, 0)
            existing_status = seen[code].get("status", "").lower().replace(" ", "_")
            existing_priority = priority.get(existing_status, 0)
            
            if current_priority > existing_priority:
                seen[code] = course
    
    return list(seen.values())


def flag_low_confidence_courses(
    courses: List[Dict[str, Any]], 
    threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Flag courses with low confidence scores for manual review.
    
    Args:
        courses: List of course dicts with optional 'confidence' key
        threshold: Minimum confidence score (0.0-1.0)
        
    Returns:
        List of flagged courses
    """
    flagged = []
    for course in courses:
        confidence = course.get("confidence", 1.0)
        if confidence < threshold:
            flagged.append(course)
    return flagged
