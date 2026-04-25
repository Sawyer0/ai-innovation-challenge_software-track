import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd()))

from app.services.catalog_loader import load_rules

if __name__ == "__main__":
    rules_path = "data/rules.json"
    if os.path.exists(rules_path):
        load_rules(rules_path)
        print("Done!")
    else:
        print(f"Error: {rules_path} not found.")
