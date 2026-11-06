"""Personal identifiers are removed from transcript text before any AI call."""

import io
import itertools

import pytest
from PIL import Image

from app.infrastructure.ai.documents import identifier_boxes, render_pdf_pages
from app.infrastructure.ai.redaction import REDACTED, find_identifier_spans, redact_text
from tests.pdf_factory import (
    FAKE_IDENTIFIERS,
    SAMPLE_ROWS,
    header_transcript_rows,
    image_pdf,
    text_pdf,
)

pytestmark = pytest.mark.unit

HEADER_TEXT = "\n".join(header_transcript_rows())


def test_cunyfirst_header_identifiers_are_redacted():
    redacted = redact_text(HEADER_TEXT)

    for identifier in FAKE_IDENTIFIERS:
        assert identifier.lower() not in redacted.lower(), identifier
    assert "Name: [REDACTED]" in redacted
    assert "Student ID: [REDACTED]" in redacted
    assert "Birthdate: [REDACTED]" in redacted


def test_course_rows_and_program_survive_redaction():
    redacted = redact_text(HEADER_TEXT)

    for row in SAMPLE_ROWS:
        assert row in redacted
    assert "Print Date: 11/05/2026" in redacted


def test_name_repeated_in_a_footer_is_redacted_too():
    redacted = redact_text(HEADER_TEXT)

    assert redacted.splitlines()[-1].startswith(REDACTED)


@pytest.mark.parametrize(
    "line",
    [
        "Contact: someone.else@school.cuny.edu",
        "Call 646-555-0100 for help",
        "SSN 123-45-6789",
        "Ref 12345678",
        "Bronx, NY 10452",
    ],
)
def test_unlabelled_identifiers_are_found_anywhere(line):
    assert REDACTED in redact_text(line)


@pytest.mark.parametrize(
    "line",
    [
        "MAT  206        Precalculus                      4.00       4.00    B+",
        "Term GPA: 3.600   Term Total: 10.00  10.00",
        "Academic Standing Effective 01/23/2025: Good Academic Standing",
        "Program: Computer Science AS   Plan: Computer Science Major",
        "Course Name: Introduction to Computing",
        "2025 Fall Term   Computer Science Major",
    ],
)
def test_transcript_rows_are_left_alone(line):
    assert redact_text(line) == line


def test_fields_sharing_a_line_are_each_redacted():
    redacted = redact_text("Student ID: 24681357 Birthdate: 03/14")

    assert redacted == "Student ID: [REDACTED] Birthdate: [REDACTED]"


def test_windows_line_endings_keep_their_newlines():
    assert redact_text("Name: Jordana Q\r\nMAT 206 Precalculus") == (
        "Name: [REDACTED]\r\nMAT 206 Precalculus"
    )


def test_spans_are_sorted_and_do_not_overlap():
    spans = find_identifier_spans(HEADER_TEXT)

    assert spans == sorted(spans)
    assert all(a_end < b_start for (_, a_end), (b_start, _) in itertools.pairwise(spans))


def _dark(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    """Mean brightness (0 black .. 255 white) of a region."""
    region = image.crop(box).convert("L")
    pixels = list(region.getdata())
    return sum(pixels) / len(pixels)


def test_rendered_text_pdf_has_identifiers_blacked_out():
    import pypdfium2 as pdfium

    data = text_pdf(header_transcript_rows())
    pdf = pdfium.PdfDocument(data)
    try:
        page = pdf[0]
        boxes = identifier_boxes(page)
        _, page_height = page.get_size()
        # One box per identifier value, plus the repeated name in the footer.
        assert len(boxes) >= 7
        (image_bytes,) = render_pdf_pages(data)
        image = Image.open(io.BytesIO(image_bytes))
        scale = image.size[1] / page_height
        for left, bottom, right, top in boxes:
            inner = (
                int(left * scale) + 1,
                int((page_height - top) * scale) + 1,
                int(right * scale) - 1,
                int((page_height - bottom) * scale) - 1,
            )
            assert _dark(image, inner) < 40
    finally:
        pdf.close()


def test_rendered_course_rows_are_not_blacked_out():
    (plain,) = render_pdf_pages(text_pdf())
    (with_header,) = render_pdf_pages(text_pdf(SAMPLE_ROWS))
    image = Image.open(io.BytesIO(plain))

    # No identifiers: rendering is unchanged and mostly white.
    assert plain == with_header
    assert _dark(image, (0, 0, image.size[0], image.size[1])) > 200


def test_scanned_page_has_nothing_to_locate():
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(image_pdf())
    try:
        assert identifier_boxes(pdf[0]) == []
    finally:
        pdf.close()
