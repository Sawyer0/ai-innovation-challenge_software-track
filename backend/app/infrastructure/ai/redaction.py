"""Find and remove personal identifiers in transcript text before it reaches an AI provider.

Advising needs the courses, grades, terms and program, never who the student is.
CUNYfirst transcripts open with a header block (Name, Student ID, Birthdate,
Student Address, ...); these deterministic rules locate those values so they can be
replaced in the text layer or blacked out on rendered pages. Nothing here logs or
returns the identifiers themselves.

Limits: the rules work on text. A scan or a screenshot has no text to search, so
its pixels can't be redacted here; the prompt and the output filter still keep
identifiers out of what the app asks for and returns.
"""

import re

REDACTED = "[REDACTED]"

# Labels whose value is an identifier. Distinctive labels count anywhere on a line
# (text layers often join header fields with a single space); generic ones such as
# "Name" or "ID" only at the start of a line or after a wide gap, so "Course Name:"
# mid-line is left alone.
_STRONG_LABEL = (
    r"(?:"
    r"(?:student|full|legal|preferred)\s+name"
    r"|student\s+(?:id|number)(?:\s*(?:no\.?|number|#))?"
    r"|empl\s*id|emplid|cunyfirst\s+id"
    r"|ssn|social\s+security(?:\s+(?:no\.?|number))?"
    r"|birth\s*date|birthday|date\s+of\s+birth|dob"
    r"|(?:student\s+|mailing\s+|home\s+|permanent\s+|street\s+)?address(?:\s+line\s*\d)?"
    r"|e-?mail(?:\s+address)?"
    r"|(?:home\s+|cell\s+|mobile\s+)?(?:phone|telephone)(?:\s+(?:no\.?|number))?"
    r")"
)
_WEAK_LABEL = r"(?:name|id(?:\s*(?:no\.?|number|#))?|street|city(?:\s*/\s*state)?|zip(?:\s*code)?|mobile|cell)"
_ANY_LABEL = rf"(?:{_STRONG_LABEL}|{_WEAK_LABEL})"
_LABELED_VALUE = re.compile(
    rf"(?:(?:^|(?<=\s)){_STRONG_LABEL}|(?:^|(?<=\s\s)|(?<=\t)){_WEAK_LABEL})"
    rf"[ \t]*[:#][ \t]*(?P<value>[^\r\n]*?)[ \t]*(?=[ \t]+{_ANY_LABEL}[ \t]*[:#]|\r?$)",
    re.IGNORECASE | re.MULTILINE,
)
_ADDRESS_LABEL = re.compile(r"address|street", re.IGNORECASE)
_NAME_LABEL = re.compile(r"name", re.IGNORECASE)

# Identifiers that are recognisable anywhere, labelled or not.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w.])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w.])")
_SSN = re.compile(r"(?<![\w.])\d{3}-\d{2}-\d{4}(?![\w.])")
# CUNY EMPLIDs are 8 digits; nothing else on a transcript is a bare 8-digit number.
_EMPLID = re.compile(r"(?<![\w./-])\d{8}(?![\w./-])")
# "New York, NY 10007" / "Bronx NY 10452-1234": the second line of a mailing address.
_CITY_STATE_ZIP = re.compile(
    r"^[ \t]*[A-Za-z][A-Za-z .'-]*,?[ \t]+[A-Z]{2}[ \t]+\d{5}(?:-\d{4})?[ \t]*(?=\r?$)",
    re.MULTILINE,
)
_ZIP_PLUS_4 = re.compile(r"(?<![\w-])\d{5}-\d{4}(?![\w-])")

_NAME_TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]+")
# Words that can sit in a name field but are too common to scrub everywhere.
_NAME_STOPWORDS = {"jr", "sr", "ii", "iii", "iv", "mr", "ms", "mrs", "dr"}


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(s for s in spans if s[1] > s[0]):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _next_line_span(text: str, position: int) -> tuple[int, int] | None:
    """The next non-blank line after ``position`` (an address's second line)."""
    newline = text.find("\n", position)
    while newline != -1:
        start = newline + 1
        end = text.find("\n", start)
        end = len(text) if end == -1 else end
        if end > start and text[end - 1] == "\r":
            end -= 1
        line = text[start:end]
        if line.strip():
            # Only take it when it looks like the rest of an address, not a new field.
            if re.search(r"\d{5}|,", line) and not re.search(r"[:#]", line):
                return (start, end)
            return None
        newline = text.find("\n", start)
    return None


def find_identifier_spans(text: str) -> list[tuple[int, int]]:
    """Character ranges in ``text`` that hold personal identifiers, merged and sorted."""
    spans: list[tuple[int, int]] = []
    name_tokens: set[str] = set()
    labelled_values: set[str] = set()

    for match in _LABELED_VALUE.finditer(text):
        value = match.group("value")
        if not value.strip():
            continue
        spans.append(match.span("value"))
        label = match.group(0)[: match.start("value") - match.start()]
        if _NAME_LABEL.search(label):
            name_tokens.update(
                t.lower()
                for t in _NAME_TOKEN.findall(value)
                if len(t) >= 2 and t.lower() not in _NAME_STOPWORDS
            )
        elif len(value.strip()) >= 4:
            labelled_values.add(value.strip())
        if _ADDRESS_LABEL.search(label):
            follow = _next_line_span(text, match.end())
            if follow:
                spans.append(follow)

    for pattern in (_EMAIL, _PHONE, _SSN, _EMPLID, _CITY_STATE_ZIP, _ZIP_PLUS_4):
        spans.extend(m.span() for m in pattern.finditer(text))

    # The same name or ID can repeat elsewhere (page headers, footers).
    for token in name_tokens:
        spans.extend(
            m.span()
            for m in re.finditer(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, re.I)
        )
    for value in labelled_values:
        spans.extend(m.span() for m in re.finditer(re.escape(value), text))

    return _merge(spans)


def redact_text(text: str) -> str:
    """``text`` with every personal identifier replaced by ``[REDACTED]``."""
    out: list[str] = []
    cursor = 0
    for start, end in find_identifier_spans(text):
        out.append(text[cursor:start])
        out.append(REDACTED)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)
