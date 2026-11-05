"""Vercel Python function entry point: serves the FastAPI backend under /api/*.

vercel.json rewrites every /api/* request here; FastAPI routes on the original path.
"""

import importlib
import json
import os
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# The deployment filesystem is read-only except /tmp. Start each instance from the
# pre-built catalog database (backend/scripts/build_catalog_db.py) so cold starts skip
# the slow JSON import. Student sessions written here are ephemeral: they live only as
# long as this function instance.
_DB_PATH = Path("/tmp/dja.db")
_SEED_DB = BACKEND_DIR / "data" / "catalog.sqlite"
if not _DB_PATH.exists() and _SEED_DB.exists():
    shutil.copyfile(_SEED_DB, _DB_PATH)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_DB_PATH}")
os.environ.setdefault("APP_ENV", "production")
# Vercel sets X-Real-IP / X-Forwarded-For itself, so they are safe to trust here.
os.environ.setdefault("TRUST_PROXY_HEADERS", "true")

# Same-origin in production; allow only this deployment's own hostnames.
_hosts = {
    os.environ.get(name)
    for name in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL", "VERCEL_URL")
}
_origins = sorted(f"https://{host}" for host in _hosts if host)
if _origins:
    os.environ.setdefault("CORS_ORIGINS", json.dumps(_origins))

# Imported only now: app.config reads the environment set above at import time.
app = importlib.import_module("app.main").app

# Don't rely on the ASGI lifespan running; this is idempotent on the pre-built DB.
importlib.import_module("app.services.catalog_loader").initialize_database()

__all__ = ["app"]
