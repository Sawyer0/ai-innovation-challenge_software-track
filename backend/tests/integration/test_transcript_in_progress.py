"""Current-term courses: no grade means in progress, with credits from the catalog."""

from decimal import Decimal

import pytest

from app import models
from tests.integration.transcript_helpers import course, upload
from tests.pdf_factory import text_pdf

pytestmark = pytest.mark.integration


class TestInProgressCourses:
    def test_ungraded_course_is_in_progress_with_catalog_credits(
        self, client, db, session_id, groq_like
    ):
        db.add(models.Course(code="MAT 301", title="Calculus I", credits=Decimal("4")))
        db.add(models.Course(code="CHE 201", title="Chemistry I", credits=Decimal("4")))
        db.commit()
        groq_like.queue(
            {
                "courses": [
                    course("MAT 301", grade=None, credits=0, semester_taken="2026 Fall Term"),
                    course("ENG 101", grade="IP", credits=3, status="in-progress"),
                    # contact hours misread as credits; the catalog wins
                    course("CHE 201", grade="", credits=7, status="completed"),
                    course("CSC 103", grade="A", credits=3),
                    course("HIS 101", grade="W", credits=0, status="withdrawn"),
                ]
            }
        )

        response = upload(client, session_id, text_pdf())

        courses = {c["course_code"]: c for c in response.json()["courses"]}
        assert (courses["MAT 301"]["status"], courses["MAT 301"]["credits"]) == ("in-progress", 4)
        assert courses["MAT 301"]["semester_taken"] == "Fall 2026"
        assert (courses["ENG 101"]["status"], courses["ENG 101"]["grade"]) == ("in-progress", None)
        assert courses["ENG 101"]["credits"] == 3  # not in the catalog: transcript value kept
        assert (courses["CHE 201"]["status"], courses["CHE 201"]["credits"]) == ("in-progress", 4)
        assert courses["CSC 103"]["status"] == "completed"
        assert courses["HIS 101"]["status"] == "withdrawn"
