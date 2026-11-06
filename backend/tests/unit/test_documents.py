"""PDF handling for providers without PDF input: text layer checks and page rendering."""

import io

import pytest
from PIL import Image

from app.infrastructure.ai.documents import (
    ENCRYPTED_PDF_MESSAGE,
    MAX_PDF_PAGES_AS_IMAGES,
    PAGE_IMAGE_MAX_SIDE,
    UnreadableDocumentError,
    extract_pdf_text,
    pdf_text_is_usable,
    render_pdf_pages,
)
from tests.pdf_factory import image_pdf, locked_pdf, text_pdf

pytestmark = pytest.mark.unit


def test_text_layer_is_extracted_and_usable():
    text = extract_pdf_text(text_pdf())

    assert "MAT  206" in text
    assert pdf_text_is_usable(text)


def test_image_only_pdf_has_no_text():
    assert extract_pdf_text(image_pdf()) == ""


@pytest.mark.parametrize(
    "text",
    [
        "",
        "MAT 206 Precalculus",  # too short to be a transcript
        "\x00\x01 ÿþ garbled glyph soup " * 20,  # long but nothing like a course code
    ],
)
def test_unusable_text(text):
    assert not pdf_text_is_usable(text)


def test_malformed_pdf_text_extraction_returns_empty():
    assert extract_pdf_text(b"%PDF-1.4\nnot really a pdf") == ""


def test_empty_password_pdf_is_opened():
    # CUNYfirst transcripts are encrypted with an empty user password.
    assert pdf_text_is_usable(extract_pdf_text(locked_pdf("")))


def test_password_protected_pdf_has_a_clear_message():
    with pytest.raises(UnreadableDocumentError) as err:
        extract_pdf_text(locked_pdf("secret"))
    assert str(err.value) == ENCRYPTED_PDF_MESSAGE

    with pytest.raises(UnreadableDocumentError, match="password-protected"):
        render_pdf_pages(locked_pdf("secret"))


def test_malformed_pdf_cannot_be_rendered():
    with pytest.raises(UnreadableDocumentError, match="couldn't be opened"):
        render_pdf_pages(b"%PDF-1.4\nnot really a pdf")


def test_pages_render_as_downscaled_jpegs_capped_at_max_pages():
    pages = render_pdf_pages(image_pdf(pages=MAX_PDF_PAGES_AS_IMAGES + 2))

    assert len(pages) == MAX_PDF_PAGES_AS_IMAGES
    for page in pages:
        image = Image.open(io.BytesIO(page))
        assert image.format == "JPEG"
        assert max(image.size) <= PAGE_IMAGE_MAX_SIDE
        assert len(page) < 1_000_000
