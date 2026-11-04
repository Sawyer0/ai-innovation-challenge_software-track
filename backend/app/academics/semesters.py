"""Academic calendar helpers: current and next semester, academic year."""

from datetime import datetime


def get_current_academic_year() -> int:
    """Get the current academic year (e.g., 2024 for 2024-2025)."""
    now = datetime.now()
    # Academic year starts in Fall (September)
    if now.month >= 9:
        return now.year
    return now.year - 1


def get_next_semester() -> str:
    """
    Calculate the next academic semester based on current date.

    Academic calendar:
    - Fall: September - December
    - Winter (optional): January
    - Spring: January - May
    - Summer: May - August

    Returns:
        String like "Fall 2024" or "Spring 2025"
    """
    now = datetime.now()
    month = now.month
    year = now.year

    # Determine next semester based on current month
    if month in [9, 10, 11, 12]:  # Fall - next is Spring
        return f"Spring {year + 1}"
    elif month in [1, 2, 3, 4, 5]:  # Spring/Spring - next is Summer or Fall
        if month <= 3:  # Early Spring - next is Summer
            return f"Summer {year}"
        else:  # Late Spring - next is Fall
            return f"Fall {year}"
    else:  # Summer (May-August) - next is Fall
        return f"Fall {year}"


def get_current_semester() -> str:
    """Get the current academic semester."""
    now = datetime.now()
    month = now.month
    year = now.year

    if month in [9, 10, 11, 12]:
        return f"Fall {year}"
    elif month in [1, 2, 3, 4, 5]:
        return f"Spring {year}"
    else:
        return f"Summer {year}"


def parse_semester(semester_str: str) -> tuple[str, int]:
    """
    Parse a semester string like 'Fall 2024' into (term, year).

    Args:
        semester_str: String like "Fall 2024" or "Spring 2025"

    Returns:
        Tuple of (term, year) like ("Fall", 2024)
    """
    parts = semester_str.split()
    term = parts[0]
    year = int(parts[1])
    return term, year
