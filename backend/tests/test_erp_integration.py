"""P4-3 · End-to-end Core↔ERP webhook integration.

Fires the SAME signed webhooks the execution engine sends (built via
backend.shared.webhooks._build_payload + HMAC) at a *running* ERP service and
verifies the double-entry ledger, fee/VAT entries, and idempotency.

Auto-skips when ERP is not reachable, so the normal unit-test run is unaffected.
To run it for real:

    docker compose up -d           # postgres + redis
    cd erp && npm start            # ERP on :5001 (loads erp/.env)
    cd backend && python -m pytest tests/test_erp_integration.py -v
"""
import hashlib
import hmac
import json
import os
import uuid

import httpx
import pytest

from backend.shared.webhooks import _build_payload

ERP_BASE = os.getenv("ERP_BASE_URL", "http://localhost:5001")
ERP_WEBHOOK_URL = os.getenv("ERP_WEBHOOK_URL", f"{ERP_BASE}/webhook/trade-event")


def _load_erp_env() -> dict:
    """Pull ERP_API_KEY / ERP_WEBHOOK_SECRET from the env, falling back to
    parsing erp/.env so the test 'just works' against a locally-running ERP."""
    keys = {k: os.getenv(k) for k in ("ERP_API_KEY", "ERP_WEBHOOK_SECRET")}
    if all(keys.values()):
        return keys
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "erp", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() in keys and not keys[k.strip()]:
                    keys[k.strip()] = v.strip()
    return keys


_ERP_ENV = _load_erp_env()


def _erp_up() -> bool:
    try:
        r = httpx.get(f"{ERP_BASE}/health", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _erp_up() or not _ERP_ENV.get("ERP_API_KEY"),
    reason="ERP service not running on :5001 (or ERP_API_KEY unset) — integration test skipped",
)


def _post_event(event_type: str, event_data: dict, trade_id: str, idemp_key: str):
    payload = _build_payload(event_type, event_data, trade_id)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=False)
    sig = hmac.new(
        _ERP_ENV["ERP_WEBHOOK_SECRET"].encode(), raw.encode(), hashlib.sha256
    ).hexdigest()
    headers = {
        "Idempotency-Key": idemp_key,
        "X-Api-Key": _ERP_ENV["ERP_API_KEY"],
        "X-Signature": f"sha256={sig}",
        "Content-Type": "application/json",
    }
    return httpx.post(ERP_WEBHOOK_URL, content=raw, headers=headers, timeout=5.0)


def _get(path: str):
    return httpx.get(
        f"{ERP_BASE}{path}",
        headers={"X-Api-Key": _ERP_ENV["ERP_API_KEY"]},
        timeout=5.0,
    )


def test_full_trade_lifecycle_double_entry_and_idempotency():
    trade_id = f"itest_{uuid.uuid4().hex[:12]}"

    # 1) Open — XAUUSD BUY 0.1 lot @ 2000
    r = _post_event(
        "trade.opened",
        {"ticker": "XAUUSD", "action": "BUY", "entry_price": 2000.0, "lot_size": 0.1},
        trade_id, str(uuid.uuid4()),
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    # 2) Close — exit 2010, realized PnL 100.0 (contractSize-correct), fee 1.61
    r = _post_event(
        "trade.pnl_realized",
        {
            "ticker": "XAUUSD", "action": "BUY", "entry_price": 2000.0,
            "exit_price": 2010.0, "lot_size": 0.1, "realized_pnl": 100.0, "fee": 1.61,
        },
        trade_id, str(uuid.uuid4()),
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    # 3) Ledger entries for this trade must be balanced double-entry
    led = _get("/api/ledger?limit=200").json()["ledger"]
    rows = [e for e in led if e.get("trade_id") == trade_id]
    assert rows, "no ledger rows recorded for the trade"

    pnl_rows = [e for e in rows if e["event"] in ("trade.pnl_realized", "trade.closed")]
    assert pnl_rows, "no PnL ledger entry"
    pnl_entry = pnl_rows[0]
    assert pnl_entry["pnl"] == pytest.approx(100.0)
    # Debit == Credit (balanced)
    assert pnl_entry["debit"]["amount"] == pytest.approx(pnl_entry["credit"]["amount"])
    assert pnl_entry["debit"]["amount"] == pytest.approx(100.0)

    # Fee + VAT entries exist and are non-zero (P0-2 — fees now flow through)
    fee_rows = [e for e in rows if e["event"] == "fee.recorded"]
    vat_rows = [e for e in rows if e["event"] == "tax.vat_input"]
    assert fee_rows and fee_rows[0]["debit"]["amount"] == pytest.approx(1.61)
    assert vat_rows and vat_rows[0]["debit"]["amount"] == pytest.approx(round(1.61 * 0.07, 2))

    # 4) Closed trade visible in /api/trades with the correct realized PnL
    trades = _get(f"/api/trades?symbol=XAUUSD").json()["trades"]
    mine = [t for t in trades if t["tradeId"] == trade_id]
    assert mine and mine[0]["realizedPnl"] == pytest.approx(100.0)
    assert mine[0]["result"] == "WIN"

    # 5) Idempotency — replaying the close with the same key must NOT double-book
    same_key = str(uuid.uuid4())
    a = _post_event(
        "trade.pnl_realized",
        {"ticker": "XAUUSD", "action": "BUY", "entry_price": 2000.0,
         "exit_price": 2010.0, "lot_size": 0.1, "realized_pnl": 100.0, "fee": 1.61},
        trade_id, same_key,
    )
    b = _post_event(
        "trade.pnl_realized",
        {"ticker": "XAUUSD", "action": "BUY", "entry_price": 2000.0,
         "exit_price": 2010.0, "lot_size": 0.1, "realized_pnl": 100.0, "fee": 1.61},
        trade_id, same_key,
    )
    assert a.status_code == 200 and b.status_code == 200
    assert b.json().get("duplicate") is True, "idempotency key should mark replay as duplicate"
