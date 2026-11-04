"""Re-import data/rules.json. Run from backend/: python -m app.scripts.reload_rules"""

from ..services.catalog_loader import DATA_DIR, load_rules


def main() -> None:
    rules_path = DATA_DIR / "rules.json"
    if not rules_path.exists():
        print(f"Error: {rules_path} not found.")
        return
    load_rules(str(rules_path))
    print("Done!")


if __name__ == "__main__":
    main()
