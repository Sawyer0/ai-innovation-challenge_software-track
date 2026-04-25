import sys
import os
from sqlalchemy import func

# Add the root directory to sys.path to allow importing from 'app'
# Assuming the script is in backend/app/scripts/
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from app.database import SessionLocal
from app.models import Program, Course, AcademicPolicy

def check_uniqueness(model, code_attr, name: str):
    """
    Checks for duplicate codes in a given model.
    """
    session = SessionLocal()
    try:
        # Group by the code attribute and count occurrences
        attr = getattr(model, code_attr)
        duplicates = (
            session.query(attr, func.count(attr))
            .group_by(attr)
            .having(func.count(attr) > 1)
            .all()
        )

        if not duplicates:
            print(f"[OK] All {name} codes are unique.")
        else:
            print(f"[FAIL] Found {len(duplicates)} duplicate groups in {name} codes:")
            for code, count in duplicates:
                print(f"   - Code: '{code}', Count: {count}")
                
        # Basic stats
        total_count = session.query(model).count()
        unique_count = session.query(attr).distinct().count()
        print(f"[STATS] {name}: Total Records = {total_count}, Unique Codes = {unique_count}")
        
    except Exception as e:
        print(f"[ERROR] Error checking {name}: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    print("\n" + "="*40)
    print("      DATABASE UNIQUENESS CHECK")
    print("="*40)
    
    print("\nChecking Program codes...")
    check_uniqueness(Program, "program_code", "Program")
    
    print("\n" + "-"*40)
    
    print("\nChecking Course codes...")
    check_uniqueness(Course, "code", "Course")
    
    print("\n" + "-"*40)
    
    print("\nChecking Academic Policy codes...")
    check_uniqueness(AcademicPolicy, "policy_code", "AcademicPolicy")
    
    print("\n" + "="*40 + "\n")
