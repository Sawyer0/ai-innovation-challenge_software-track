"""
Prerequisite text parser.

Extracts structured course codes and logic groups from free-text
prerequisite descriptions scraped from the BMCC catalog.

Responsibility (SRP): Parse raw prerequisite text → structured entries.
No database access, no validation models — pure text processing.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict


# BMCC course codes: 2-4 uppercase letters + optional space + 3-4 digits + optional .N suffix
# Matches: MAT 157, CSC 211, ENG100.5, ESL 94RW (captures ESL 94), MAT 206.5
COURSE_CODE_RE = re.compile(
    r'\b([A-Z]{2,4})\s*(\d{3,4}(?:\.\d{1,2})?)\b'
)

# Corequisite indicators
COREQ_RE = re.compile(
    r'\b(?:co-?requisite|concurrent(?:ly)?)\b', re.IGNORECASE
)

# Student attribute indicators (Proficiency indexes, student groups)
ATTRIBUTE_RE = re.compile(
    r'(?P<name>English Proficiency|Math Proficiency|Writing Index|Math Index|English Index|ASAP|Honors)\s*(?:Index|Score|Student)?\s*(?:of|at)?\s*(?P<value>\d+\+?|Student|Group)?',
    re.IGNORECASE
)


class CourseCodeIndex:
    """
    Fuzzy lookup index for course codes.

    Responsibility (SRP): Normalize and resolve course code variations
    against a known catalog of valid codes.

    Handles:
      - Whitespace differences: "ESL62" → "ESL 62"
      - Case differences: "mat 157" → "MAT 157"
      - Suffix stripping: "ART 102H" → "ART 102" (honors variant)
      - Wildcard patterns: "ART *" → returns None (not a real course)
    """

    def __init__(self, course_map: dict):
        """
        Build the index from a course_map (code → Course object).
        Stores the original map and builds a normalized lookup table.
        """
        self._course_map = course_map
        self._normalized: Dict[str, str] = {}

        for code in course_map.keys():
            self._normalized[self._normalize(code)] = code

    @staticmethod
    def _normalize(code: str) -> str:
        """Reduce a course code to a canonical form for fuzzy matching."""
        return re.sub(r'\s+', '', code.strip().upper())

    def lookup(self, raw_code: str):
        """
        Resolve a raw code to a Course object from the catalog.
        Returns the Course object or None if no match.
        """
        if not raw_code or '*' in raw_code:
            return None

        # Try normalized match
        key = self._normalize(raw_code)
        if key in self._normalized:
            return self._course_map[self._normalized[key]]

        # Try stripping trailing letter suffix (e.g., "ART 102H" → "ART102")
        stripped = re.sub(r'[A-Z]+$', '', key)
        if stripped and stripped != key and stripped in self._normalized:
            return self._course_map[self._normalized[stripped]]

        return None


@dataclass
class ParsedPrerequisite:
    """A single structured prerequisite entry extracted from raw text."""
    course_code: Optional[str]
    logic_group: int
    is_corequisite: bool
    notes: str
    
    # New fields for indexed attributes
    is_attribute: bool = False
    attribute_name: Optional[str] = None
    attribute_value: Optional[str] = None


def _normalize_code(subject: str, number: str) -> str:
    """Normalize to 'SUBJ NNN' format with single space."""
    return f"{subject.upper().strip()} {number.strip()}"


def _extract_codes_with_positions(text: str) -> List[tuple]:
    """Find all course codes in text with their start positions."""
    results = []
    for match in COURSE_CODE_RE.finditer(text):
        code = _normalize_code(match.group(1), match.group(2))
        results.append((code, match.start(), match.end()))
    return results


def _get_text_between(text: str, end_a: int, start_b: int) -> str:
    """Get the connector text between two course code matches."""
    return text[end_a:start_b].strip().lower()


def parse_prerequisite_text(raw_text: str) -> List[ParsedPrerequisite]:
    """
    Parse raw prerequisite text into structured prerequisite entries.

    Grouping logic:
      - Commas, semicolons, 'and' between course codes → AND (separate groups)
      - 'or' between course codes → OR (same group, alternatives)
      - No course codes found → single entry with notes only

    Examples:
        "ACC 222 and ACC 241"
            → group 1: ACC 222, group 2: ACC 241  (need both)

        "ENG 201 or ENG 121"
            → group 1: ENG 201, group 1: ENG 121  (pick one)

        "ESC 130, MAT 302 and PHY 225"
            → group 1: ESC 130, group 2: MAT 302, group 3: PHY 225

        "ENG 201 and (ENG 116 or ENG 311)"
            → group 1: ENG 201, group 2: ENG 116, group 2: ENG 311

        "English Proficiency Index 55+"
            → course_code=None, notes="English Proficiency Index 55+"
    """
    if not raw_text or not raw_text.strip():
        return []

    text = raw_text.strip()
    is_corequisite = bool(COREQ_RE.search(text))

    codes = _extract_codes_with_positions(text)

    # If no codes found, check for attributes
    if not codes:
        attr_match = ATTRIBUTE_RE.search(text)
        if attr_match:
            return [ParsedPrerequisite(
                course_code=None,
                logic_group=1,
                is_corequisite=is_corequisite,
                notes=text,
                is_attribute=True,
                attribute_name=attr_match.group("name"),
                attribute_value=attr_match.group("value")
            )]
        
        # No codes and no attributes → notes-only entry
        return [ParsedPrerequisite(
            course_code=None,
            logic_group=1,
            is_corequisite=is_corequisite,
            notes=text
        )]

    # Single course code → straightforward
    if len(codes) == 1:
        return [ParsedPrerequisite(
            course_code=codes[0][0],
            logic_group=1,
            is_corequisite=is_corequisite,
            notes=text
        )]

    # Multiple codes → analyze connectors between each consecutive pair
    results = []
    current_group = 1

    for i, (code, start, end) in enumerate(codes):
        if i == 0:
            results.append(ParsedPrerequisite(
                course_code=code,
                logic_group=current_group,
                is_corequisite=is_corequisite,
                notes=text
            ))
            continue

        # Look at the text between previous code and this one
        prev_end = codes[i - 1][2]
        connector = _get_text_between(text, prev_end, start)

        # Determine if this is OR (same group) or AND (new group)
        # "or" → same group (alternatives)
        # "and", ",", ";" → new group (all required)
        if 'or' in connector.split():
            # Same group as previous — OR alternative
            results.append(ParsedPrerequisite(
                course_code=code,
                logic_group=current_group,
                is_corequisite=is_corequisite,
                notes=text
            ))
        else:
            # New group — AND requirement
            current_group += 1
            results.append(ParsedPrerequisite(
                course_code=code,
                logic_group=current_group,
                is_corequisite=is_corequisite,
                notes=text
            ))

    return results


def parse_wildcard(raw_code: str) -> Optional[dict]:
    """
    Parse a wildcard course code (e.g., "ART *", "POL 1*").
    Returns a dict with subject and level prefix.
    """
    if not raw_code or '*' not in raw_code:
        return None
    
    # Clean up and normalize
    clean = raw_code.strip().upper()
    
    # Match subject and optional level
    # "ART *" -> subject="ART", level=None
    # "POL 1*" -> subject="POL", level="1"
    match = re.match(r'^([A-Z]{2,4})\s*(\d+)?\*$', clean)
    if match:
        return {
            "subject": match.group(1),
            "level": match.group(2)
        }
    return None
