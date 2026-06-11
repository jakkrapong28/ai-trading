import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.shared.database.core import engine, Base
from backend.shared.database.models import *

def main():
    print("Dropping all database tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("Recreating all database tables...")
        Base.metadata.create_all(bind=engine)
        print("Database schema successfully recreated!")
    except Exception as e:
        print(f"Error during database recreation: {e}")

if __name__ == "__main__":
    main()
