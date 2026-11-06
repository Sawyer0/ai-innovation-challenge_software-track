"""Transcript upload through a Groq-like provider (no PDF input)."""

import io

import pytest
from PIL import Image

from app.infrastructure.ai.documents import ENCRYPTED_PDF_MESSAGE
from tests.integration.transcript_helpers import course, upload
from tests.pdf_factory import image_pdf, locked_pdf, text_pdf

pytestmark = pytest.mark.integration


class TestPdfRouting:
    def test_text_pdf_is_sent_as_text(self, client, session_id, groq_like):
        groq_like.queue({"profile": {}, "courses": [course("MAT 206")]})

        response = upload(client, session_id, text_pdf())

        assert response.status_code == 200
        assert [c["course_code"] for c in response.json()["courses"]] == ["MAT 206"]
        (call,) = groq_like.calls
        assert "images" not in call
        assert "MAT  206" in call["prompt"]

    def test_scanned_pdf_is_read_as_page_images(self, client, session_id, groq_like):
        groq_like.queue({"profile": {"program_code": "CSC-AS"}, "courses": [course("ENG 101")]})

        response = upload(client, session_id, image_pdf(pages=1))

        assert response.status_code == 200
        assert response.json()["profile"]["program_code"] == "CSC-AS"
        (call,) = groq_like.calls
        assert call["mime_type"] == "image/jpeg"
        assert len(call["images"]) == 1
        assert Image.open(io.BytesIO(call["images"][0])).format == "JPEG"

    def test_long_scan_is_split_into_batches_and_merged(self, client, session_id, groq_like):
        groq_like.queue(
            {"profile": {"program_code": "CSC-AS"}, "courses": [course("MAT 206")]},
            {
                "profile": {"program_code": None, "cumulative_gpa": 3.5},
                "courses": [course("MAT 206"), course("CSC 103")],
            },
        )

        response = upload(client, session_id, image_pdf(pages=6))

        assert response.status_code == 200
        assert [len(c["images"]) for c in groq_like.calls] == [3, 1]  # 4-page cap, 3 per call
        data = response.json()
        assert [c["course_code"] for c in data["courses"]] == ["MAT 206", "CSC 103"]
        assert data["profile"] == {"program_code": "CSC-AS", "cumulative_gpa": 3.5}

    def test_text_that_yields_no_courses_falls_back_to_images(self, client, session_id, groq_like):
        groq_like.queue({"profile": {}, "courses": []}, {"courses": [course("CSC 103")]})

        response = upload(client, session_id, text_pdf())

        assert response.status_code == 200
        assert "images" not in groq_like.calls[0]
        assert len(groq_like.calls[1]["images"]) == 1

    def test_password_protected_pdf_is_rejected_without_calling_ai(
        self, client, session_id, groq_like
    ):
        response = upload(client, session_id, locked_pdf("secret"))

        assert response.status_code == 400
        assert response.json()["detail"] == ENCRYPTED_PDF_MESSAGE
        assert groq_like.calls == []

    def test_cunyfirst_style_empty_password_pdf_parses(self, client, session_id, groq_like):
        groq_like.queue({"courses": [course("MAT 206")]})

        assert upload(client, session_id, locked_pdf("")).status_code == 200
