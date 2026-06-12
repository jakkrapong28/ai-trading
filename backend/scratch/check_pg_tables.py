import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.shared.database.core import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Get table list
    res = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
    tables = [r[0] for r in res.fetchall()]
    print("Tables in database:", tables)
    
    for table in tables:
        print(f"\nStructure of {table}:")
        col_res = db.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table}'"))
        for col in col_res.fetchall():
            print(f"  {col[0]}: {col[1]}")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
