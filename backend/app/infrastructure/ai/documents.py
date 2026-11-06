"""Turn uploaded PDFs into something every provider can read.

Groq has no PDF input, so a PDF is sent either as its text layer or, when that is
missing or unusable (scans, photos saved as PDF, odd encodings), as page images for
the vision model.
"""

import io
import logging
import re
from typing import Any

from PIL import ImageDraw
from pypdf import PdfReader

from .redaction import find_identifier_spans

logger = logging.getLogger(__name__)

# Below this much text, or without anything shaped like a course code, the text
# layer is treated as unusable and the pages are read as images instead.
MIN_USABLE_TEXT_CHARS = 200
_COURSE_CODE = re.compile(r"\b[A-Z]{2,4}\s{0,2}-?\d{3}[A-Z]?\b")

MAX_PDF_PAGES_AS_IMAGES = 4
# Longest side of a rendered page. Keeps a page well under the request size limit
# while staying legible for OCR.
PAGE_IMAGE_MAX_SIDE = 2200
PAGE_IMAGE_JPEG_QUALITY = 80

ENCRYPTED_PDF_MESSAGE = (
    "This PDF is password-protected, so it can't be read. Download an unlocked copy of "
    "your transcript from CUNYfirst, or upload screenshots of it instead."
)
UNREADABLE_PDF_MESSAGE = (
    "This PDF couldn't be opened; it may be damaged. Try downloading it again, or "
    "upload screenshots of your transcript instead."
)


class UnreadableDocumentError(ValueError):
    """The upload can't be read by any provider (locked or corrupt). The message is user-facing."""


def extract_pdf_text(data: bytes) -> str:
    """Return the PDF's text layer, or "" when it can't be extracted.

    CUNYfirst exports are encrypted with an empty user password; pypdf opens those.
    A PDF that needs a real password raises UnreadableDocumentError.
    """
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as e:  # unsupported encryption, missing crypto backend
                logger.warning("pypdf could not decrypt PDF: %s", e)
                return ""
            if not unlocked:
                raise UnreadableDocumentError(ENCRYPTED_PDF_MESSAGE)
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except UnreadableDocumentError:
        raise
    except Exception as e:  # malformed file, odd font encodings
        logger.warning("PDF text extraction failed: %s", e)
        return ""


def pdf_text_is_usable(text: str) -> bool:
    """True when the text layer looks like a real transcript rather than noise."""
    return len(text) >= MIN_USABLE_TEXT_CHARS and _COURSE_CODE.search(text) is not None


REDACTION_PADDING_PX = 3


def identifier_boxes(page: Any) -> list[tuple[float, float, float, float]]:
    """Boxes (left, bottom, right, top, in PDF points) around a page's identifiers.

    Uses the page's own text layer to find them, so it only works on PDFs with text;
    a scanned page has none and yields no boxes.
    """
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_range()
        boxes: list[tuple[float, float, float, float]] = []
        for start, end in find_identifier_spans(text):
            line: list[float] | None = None
            for index in range(start, min(end, textpage.count_chars())):
                if text[index].isspace():
                    continue
                left, bottom, right, top = textpage.get_charbox(index, loose=True)
                # Start a new box when the span wraps onto another line.
                if line is not None and (bottom > line[3] or top < line[1]):
                    boxes.append((line[0], line[1], line[2], line[3]))
                    line = None
                if line is None:
                    line = [left, bottom, right, top]
                else:
                    line = [
                        min(line[0], left),
                        min(line[1], bottom),
                        max(line[2], right),
                        max(line[3], top),
                    ]
            if line is not None:
                boxes.append((line[0], line[1], line[2], line[3]))
        return boxes
    finally:
        textpage.close()


def _black_out_identifiers(page: Any, image: Any, scale: float) -> None:
    """Paint over identifier text on a rendered page before it is sent anywhere."""
    _, page_height = page.get_size()
    draw = ImageDraw.Draw(image)
    pad = REDACTION_PADDING_PX
    for left, bottom, right, top in identifier_boxes(page):
        draw.rectangle(
            (
                left * scale - pad,
                (page_height - top) * scale - pad,
                right * scale + pad,
                (page_height - bottom) * scale + pad,
            ),
            fill="black",
        )


def render_pdf_pages(data: bytes, max_pages: int = MAX_PDF_PAGES_AS_IMAGES) -> list[bytes]:
    """Render the first ``max_pages`` pages to JPEG bytes for a vision model.

    Identifiers found in a page's text layer (name, student ID, birthdate, address,
    contact details) are blacked out first. Scanned pages have no text layer, so
    nothing on them can be located or blacked out.
    """
    import pypdfium2 as pdfium  # imported lazily: only scanned PDFs need it

    try:
        pdf = pdfium.PdfDocument(data, password="")
    except pdfium.PdfiumError as e:
        message = str(e).lower()
        logger.warning("pdfium could not open PDF: %s", e)
        if "password" in message:
            raise UnreadableDocumentError(ENCRYPTED_PDF_MESSAGE) from e
        raise UnreadableDocumentError(UNREADABLE_PDF_MESSAGE) from e

    try:
        images: list[bytes] = []
        for index in range(min(len(pdf), max_pages)):
            page = pdf[index]
            width, height = page.get_size()
            scale = min(PAGE_IMAGE_MAX_SIDE / max(width, height, 1), 3.0)
            image = page.render(scale=scale).to_pil().convert("RGB")
            _black_out_identifiers(page, image, scale)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=PAGE_IMAGE_JPEG_QUALITY, optimize=True)
            images.append(buffer.getvalue())
        if not images:
            raise UnreadableDocumentError(UNREADABLE_PDF_MESSAGE)
        return images
    finally:
        pdf.close()
