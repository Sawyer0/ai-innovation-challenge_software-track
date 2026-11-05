"""Build backend/data/catalog.sqlite, the pre-loaded catalog database for serverless deploys.

Loading bmcc-catalog.json into SQLite takes ~15-20 s, too slow for a cold start, so the
Vercel function copies this pre-built file to /tmp instead. Re-run after changing the
catalog JSON, rules.json, or the models:

    cd backend && python scripts/build_catalog_db.py
"""

import os
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT = BACKEND_DIR / "data" / "catalog.sqlite"


def main() -> None:
    OUTPUT.unlink(missing_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{OUTPUT}"
    sys.path.insert(0, str(BACKEND_DIR))

    from app.services.catalog_loader import initialize_database

    initialize_database()

    with sqlite3.connect(OUTPUT) as conn:
        conn.execute("VACUUM")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
