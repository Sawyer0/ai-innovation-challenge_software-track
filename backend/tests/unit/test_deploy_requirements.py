"""The root requirements.txt (read by Vercel) must list the backend's runtime packages.

Vercel can't follow "-r" includes, so the root file repeats backend/requirements.txt.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_ONLY = {"uvicorn"}


def _packages(path: Path) -> dict[str, str]:
    packages = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        assert not line.startswith("-"), f"{path.name}: Vercel can't parse {line!r}"
        name = re.split(r"[\[<>=!~ ]", line, maxsplit=1)[0].lower()
        packages[name] = line.replace(" ", "")
    return packages


def test_root_requirements_match_backend() -> None:
    backend = _packages(REPO_ROOT / "backend" / "requirements.txt")
    root = _packages(REPO_ROOT / "requirements.txt")
    expected = {name: spec for name, spec in backend.items() if name not in DEV_ONLY}
    assert root == expected
