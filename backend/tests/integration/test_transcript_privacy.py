"""No personal identifier from a transcript reaches an AI provider, a response, or a log."""

import io
import logging

import pytest
from PIL import Image

from app.prompts import TRANSCRIPT_PARSING_SYSTEM_PROMPT, TRANSCRIPT_PARSING_USER_PROMPT
from tests.integration.transcript_helpers import course, upload
from tests.pdf_factory import FAKE_IDENTIFIERS, header_transcript_rows, text_pdf

pytestmark = pytest.mark.integration


def _assert_no_identifiers(text: str) -> None:
    for identifier in FAKE_IDENTIFIERS:
        assert identifier.lower() not in text.lower(), identifier


class TestWhatProvidersSee:
    def test_text_layer_is_redacted_before_the_prompt(self, client, session_id, groq_like):
        groq_like.queue({"profile": {}, "courses": [course("MAT 206")]})

        response = upload(client, session_id, text_pdf(header_transcript_rows()))

        assert response.status_code == 200
        (call,) = groq_like.calls
        _assert_no_identifiers(call["prompt"])
        assert "[REDACTED]" in call["prompt"]
        assert "MAT  206" in call["prompt"]

    def test_providers_that_take_pdfs_get_redacted_text_not_the_file(
        self, client, session_id, ai_providers
    ):
        ai_providers.primary.queue({"profile": {}, "courses": [course("MAT 206")]})

        response = upload(client, session_id, text_pdf(header_transcript_rows()))

        assert response.status_code == 200
        (call,) = ai_providers.primary.calls
        assert "data" not in call
        _assert_no_identifiers(call["prompt"])

    def test_page_images_have_identifiers_blacked_out(self, client, session_id, groq_like):
        # The text yields no courses, so the pages are rendered and read as images.
        groq_like.queue({"profile": {}, "courses": []}, {"courses": [course("CSC 103")]})

        response = upload(client, session_id, text_pdf(header_transcript_rows()))

        assert response.status_code == 200
        (page,) = groq_like.calls[1]["images"]
        image = Image.open(io.BytesIO(page)).convert("L")
        # Black boxes cover the header values: a fully white page would mean none.
        assert min(image.getdata()) < 20

    def test_prompts_never_ask_for_identifiers(self):
        user_prompt = TRANSCRIPT_PARSING_USER_PROMPT.lower()
        assert "student profile information" not in user_prompt
        assert "do not include the student's name" in user_prompt
        assert "never read out or return the student's name" in (
            TRANSCRIPT_PARSING_SYSTEM_PROMPT.lower()
        )


class TestWhatTheApiReturns:
    def test_identifiers_a_model_returns_are_dropped(self, client, session_id, groq_like):
        groq_like.queue(
            {
                "profile": {
                    "student_name": "Jordana Testperson",
                    "student_id": "24681357",
                    "name": "Jordana Testperson",
                    "program_code": "CSC-AS",
                },
                "courses": [course("MAT 206", student_id="24681357")],
            }
        )

        response = upload(client, session_id, text_pdf(header_transcript_rows()))

        assert response.status_code == 200
        body = response.json()
        assert body["profile"]["program_code"] == "CSC-AS"
        _assert_no_identifiers(response.text)
        assert set(body["courses"][0]) == {
            "course_code",
            "course_title",
            "semester_taken",
            "credits",
            "grade",
            "status",
        }


class TestLogs:
    def test_failures_do_not_log_transcript_contents(self, client, session_id, groq_like, caplog):
        groq_like.queue(RuntimeError("echoing request: Name: Testperson,Jordana Q 24681357"))
        caplog.set_level(logging.DEBUG)

        response = upload(client, session_id, text_pdf(header_transcript_rows()))

        assert response.status_code == 502
        _assert_no_identifiers(caplog.text)
