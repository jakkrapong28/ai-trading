import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.shared.database.core import SessionLocal
from backend.shared.database.models import ERPDeliveryRecord

db = SessionLocal()
records = db.query(ERPDeliveryRecord).order_by(ERPDeliveryRecord.created_at.desc()).limit(15).all()
print(f"Total delivery records found: {db.query(ERPDeliveryRecord).count()}")
print("-" * 60)
for r in records:
    print(f"ID: {r.id}")
    print(f"Trade ID: {r.trade_id}")
    print(f"Status: {r.status}")
    print(f"Response Code: {r.response_code}")
    print(f"Response Body: {r.response_body}")
    print(f"Payload: {r.request_payload}")
    print("-" * 60)
db.close()
