"""Import the BMCC catalog (and rules.json) into the database.

Run from backend/: python -m app.scripts.import_catalog [--path data/bmcc-catalog.json]
"""

import argparse
from pathlib import Path

from ..services.catalog_loader import DATA_DIR, load_catalog, load_rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Import BMCC catalog data into the database.")
    parser.add_argument(
        "--path",
        type=Path,
        default=DATA_DIR / "bmcc-catalog.json",
        help="Path to the catalog JSON file (default: data/bmcc-catalog.json)",
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Catalog file not found at {args.path}")
        return

    load_catalog(str(args.path))

    rules_path = args.path.parent / "rules.json"
    if rules_path.exists():
        load_rules(str(rules_path))
    else:
        print(f"Note: rules.json not found at {rules_path}. Skipping rules import.")


if __name__ == "__main__":
    main()
