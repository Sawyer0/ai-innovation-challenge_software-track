import os
import argparse
from ..services.catalog_loader import load_catalog

def main():
    parser = argparse.ArgumentParser(description="Import BMCC catalog data into the database.")
    parser.add_argument("--path", type=str, help="Path to the catalog JSON file")
    parser.add_argument("--fresh", action="store_true", help="Force a fresh import (drop and recreate tables)")
    
    args = parser.parse_args()
    
    # Default path relative to the root of the project
    if not args.path:
        # We assume this script is run from the backend/ directory
        # root/bmcc-catalog.json
        args.path = os.path.join(os.getcwd(), "..", "bmcc-catalog.json")
    
    if not os.path.exists(args.path):
        # Try local data directory if not found in root
        args.path = os.path.join(os.getcwd(), "data", "bmcc-catalog.json")

    if not os.path.exists(args.path):
        print(f"Error: Catalog file not found at {args.path}")
        return

    load_catalog(args.path)

if __name__ == "__main__":
    main()
