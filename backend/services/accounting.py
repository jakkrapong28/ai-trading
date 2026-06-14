"""Accounting service — single source of truth for equity, balances, orders.

Replaces the hardcoded 45750 balance and the duplicated DB-reading logic that
lived inline in main.py. Sync core functions take a `db` session; async
wrappers run them off the event loop via asyncio.to_thread so the FastAPI
handlers never block on synchronous SQLAlchemy.
"""
import logging
from typing import List, Optional

from backend.config import STARTING_BALANCE, ACCOUNT_DISPLAY_SPLITS
from backend.core.base import trade_pnl
from backend.shared.database.core import run_db
from backend.shared.database.models import Trade, TradeStatus

logger = logging.getLogger("accounting")

_OPEN_STATUSES = [TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL]


# ── sync core (take a db session) ───────────────────────────────────────────

def closed_pnl(db) -> float:
    """Sum of realized PnL across all closed trades."""
    closed = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()
    return sum(t.realized_pnl for t in closed if t.realized_pnl)


def account_balance(db) -> float:
    """Realized account balance = starting capital + closed PnL."""
    return STARTING_BALANCE + closed_pnl(db)


def floating_pnl(db, latest_prices: dict) -> float:
    """Unrealized PnL of all open positions at current market prices."""
    total = 0.0
    for t in db.query(Trade).filter(Trade.status.in_(_OPEN_STATUSES)).all():
        cur = latest_prices.get(t.ticker)
        if not cur:
            continue
        price = cur["last_price"]
        entry = t.entry_price or 0.0
        lot = t.lot_size or 0.0
        # Single source of truth — same formula as realized PnL (contractSize-correct).
        total += trade_pnl(t.ticker, t.action.value, entry, price, lot)
    return total


def account_equity(db, latest_prices: Optional[dict] = None) -> float:
    """Equity = balance + floating PnL (floating only if prices supplied)."""
    bal = account_balance(db)
    if latest_prices:
        bal += floating_pnl(db, latest_prices)
    return bal


def display_balances(db, latest_prices: dict) -> List[dict]:
    """Per-source display split of equity/balance (cosmetic — see config)."""
    balance = account_balance(db)
    equity = balance + floating_pnl(db, latest_prices)
    return [
        {
            "source": source,
            "equity": round(equity * pct, 2),
            "balance": round(balance * pct, 2),
            "free_margin": round(balance * pct, 2),
        }
        for source, pct in ACCOUNT_DISPLAY_SPLITS.items()
    ]


def list_orders(db, limit: int = 100) -> List[dict]:
    """Recent trades as plain dicts for the dashboard."""
    trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id,
            "symbol": t.ticker,
            "action": t.action.value,
            "volume": t.lot_size,
            "entry_price": t.entry_price or 0.0,
            "exit_price": t.exit_price or 0.0,
            "sl_price": t.sl_price or 0.0,
            "tp_price": t.tp_price or 0.0,
            "pnl": t.realized_pnl or 0.0,
            "fee": t.fee or 0.0,
            "status": t.status.value,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        }
        for t in trades
    ]


# ── async wrappers (non-blocking; run sync core off the event loop) ──────────

async def get_account_equity(latest_prices: Optional[dict] = None) -> float:
    try:
        return await run_db(account_equity, latest_prices)
    except Exception as e:
        logger.error(f"get_account_equity failed: {e}")
        return STARTING_BALANCE


async def get_display_balances(latest_prices: dict) -> List[dict]:
    try:
        return await run_db(display_balances, latest_prices)
    except Exception as e:
        logger.error(f"get_display_balances failed: {e}")
        equity = STARTING_BALANCE
        return [
            {"source": s, "equity": round(equity * p, 2),
             "balance": round(equity * p, 2), "free_margin": round(equity * p, 2)}
            for s, p in ACCOUNT_DISPLAY_SPLITS.items()
        ]


async def get_orders(limit: int = 100) -> List[dict]:
    try:
        return await run_db(list_orders, limit)
    except Exception as e:
        logger.error(f"get_orders failed: {e}")
        return []
