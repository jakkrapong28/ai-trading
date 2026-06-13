"""Unified ERP webhook delivery.

Consolidates three near-identical implementations that previously lived in
main.py (×2) and engines/execution.py. HMAC-SHA256 signed, idempotent, and
fail-closed when credentials are missing. Every delivery is recorded in
ERPDeliveryRecord for auditing.
"""
import hashlib
import hmac
import json
import logging
import os
import uuid

import httpx

from backend.shared.database.core import SessionLocal
from backend.shared.database.models import ERPDeliveryRecord

logger = logging.getLogger("erp-webhook")


def _build_payload(event_type: str, event_data: dict, trade_id: str) -> dict:
    if event_type == "trade.opened":
        return {
            "event": "trade.opened",
            "data": {
                "trade_id": trade_id,
                "symbol": event_data["ticker"],
                "action": event_data["action"],
                "price": event_data.get("entry_price"),
                "volume": event_data["lot_size"],
                "lot_size": event_data["lot_size"],
            },
        }
    if event_type == "trade.pnl_realized":
        return {
            "event": "trade.pnl_realized",
            "data": {
                "trade_id": trade_id,
                "symbol": event_data["ticker"],
                "action": event_data["action"],
                "price": event_data.get("exit_price", 0),
                "exit_price": event_data.get("exit_price", 0),
                "entry_price": event_data.get("entry_price", 0),
                "volume": event_data["lot_size"],
                "lot_size": event_data["lot_size"],
                "pnl": event_data.get("realized_pnl", 0),
                "fee": 0.0,
            },
        }
    return {"event": event_type, "data": {**event_data, "trade_id": trade_id}}


async def fire_erp_webhook(event_type: str, event_data: dict, trade_id: str) -> None:
    """Deliver a signed, idempotent trade event to the ERP webhook endpoint."""
    erp_url = os.getenv("ERP_WEBHOOK_URL", "http://localhost:5001/webhook/trade-event")
    erp_api_key = os.getenv("ERP_API_KEY", "")
    erp_webhook_secret = os.getenv("ERP_WEBHOOK_SECRET", "")

    # Fail closed: never fire with a missing/placeholder secret — ERP would
    # either reject it or (worse) accept a publicly-known default key.
    if not erp_api_key or not erp_webhook_secret:
        logger.error(
            f"[ERP] Skipping webhook '{event_type}' for {trade_id}: "
            "ERP_API_KEY / ERP_WEBHOOK_SECRET not configured."
        )
        return

    idemp_key = str(uuid.uuid4())
    payload = _build_payload(event_type, event_data, trade_id)
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=False)
    sig_hex = hmac.new(
        erp_webhook_secret.encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    db = SessionLocal()
    record = ERPDeliveryRecord(
        trade_id=trade_id, idempotency_key=idemp_key, request_payload=payload
    )
    db.add(record)
    db.commit()

    headers = {
        "Idempotency-Key": idemp_key,
        "X-Api-Key": erp_api_key,
        "X-Signature": f"sha256={sig_hex}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(erp_url, content=raw_body, headers=headers, timeout=3.0)
            record.response_code = resp.status_code
            record.response_body = resp.text
            record.status = "SUCCESS" if resp.status_code < 300 else "FAILED"
            logger.debug(f"[ERP] Webhook {event_type} → {resp.status_code}")
    except Exception as e:
        record.status = "ERROR"
        record.response_body = str(e)
        logger.debug(f"ERP webhook failed (expected if ERP offline): {e}")
    finally:
        db.commit()
        db.close()
