"""The pre-built catalog database used by the Vercel deploy must match the models and data.

Rebuild it with `python scripts/build_catalog_db.py` when this fails.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from app.database import Base

pytestmark = pytest.mark.data_quality

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BUNDLED_DB = DATA_DIR / "catalog.sqlite"
SESSION_TABLES = ("student_sessions", "student_profiles", "student_courses")


@pytest.fixture(scope="module")
def conn():
    if not BUNDLED_DB.exists():
        pytest.fail(f"{BUNDLED_DB} is missing; run scripts/build_catalog_db.py")
    connection = sqlite3.connect(f"file:{BUNDLED_DB}?mode=ro", uri=True)
    yield connection
    connection.close()


def test_schema_matches_models(conn):
    for table in Base.metadata.sorted_tables:
        rows = conn.execute(f"PRAGMA table_info({table.name})").fetchall()
        assert rows, f"table {table.name} missing from bundled DB"
        assert {r[1] for r in rows} == {c.name for c in table.columns}, table.name


def test_has_no_student_data(conn):
    for table in SESSION_TABLES:
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_catalog_counts_match_json(conn):
    catalog = json.loads((DATA_DIR / "bmcc-catalog.json").read_text(encoding="utf-8"))
    course_codes = {c["code"] for c in catalog["courses"]}
    program_codes = {p["programCode"] for p in catalog["programs"]}
    assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == len(course_codes)
    assert conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0] == len(program_codes)
