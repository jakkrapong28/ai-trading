"""Real coverage for the execution monitor lifecycle (Roadmap ข้อ 5 refactor).

`_evaluate_position` was extracted out of `monitor_active_trades` so the SL/TP/
trailing logic can be driven directly with an in-memory snapshot — no event bus,
no DB session held across awaits.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _snap(**overrides):
    base = dict(
        id="t-1",
        ticker="XAUUSD",
        action="BUY",
        entry_price=2300.0,
        sl_price=2280.0,   # initial risk = 20
        tp_price=2400.0,
        lot_size=1.0,
        status=None,       # set per-test where the BE gate matters
        tp1_hit=False,
        tp2_hit=False,
        tp3_hit=False,
        highest_price=2300.0,
        lowest_price=2300.0,
        atr_at_entry=10.0,
        trailing_notified=False,
        market_regime="BULL",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _engine():
    from backend.engines.execution import ExecutionEngine
    engine = ExecutionEngine(MagicMock())
    engine.broker = MagicMock()
    engine.broker.modify_order = AsyncMock()
    engine._execute_close = AsyncMock()
    engine._update_trade = AsyncMock()
    return engine


@pytest.mark.asyncio
async def test_sl_hit_closes_position():
    from backend.config import FEATURE_FLAGS
    engine = _engine()
    snap = _snap(status="RUNNING")
    # price below SL for a BUY → full close at the SL price
    with patch.dict(FEATURE_FLAGS, {"partial_tp": False, "adaptive_trailing": True}):
        await engine._evaluate_position(snap, price=2275.0)
    engine._execute_close.assert_awaited_once_with(snap, 2280.0, "SL/Trailing Hit", close_pct=1.0)


@pytest.mark.asyncio
async def test_tp1_partial_close_and_move_to_be():
    from backend.config import FEATURE_FLAGS
    from backend.shared.database.models import TradeStatus  # noqa: F401 (import sanity)
    engine = _engine()
    snap = _snap(status="OPEN")
    # price at +1.05R with partial TP enabled → TP1 partial close + SL to entry
    with patch.dict(FEATURE_FLAGS, {"partial_tp": True}):
        await engine._evaluate_position(snap, price=2321.0)
    engine._execute_close.assert_awaited_once_with(snap, 2321.0, "TP1 Hit (1.0R)", close_pct=0.5)
    engine.broker.modify_order.assert_any_await("t-1", stop_loss=2300.0)
    assert snap.tp1_hit is True
    engine._update_trade.assert_any_await("t-1", tp1_hit=True)
    engine._update_trade.assert_any_await("t-1", sl_price=2300.0)


@pytest.mark.asyncio
async def test_adaptive_trailing_2atr_at_1_8r():
    from backend.config import FEATURE_FLAGS
    from backend.shared.database.models import TradeStatus
    engine = _engine()
    snap = _snap(status=TradeStatus.RUNNING)  # already running so BE gate is skipped
    # +1.8R, ATR 10 → trailing SL = price - 2*ATR = 2316, more favorable than 2280
    with patch.dict(FEATURE_FLAGS, {"partial_tp": False, "adaptive_trailing": True}):
        await engine._evaluate_position(snap, price=2336.0)
    engine.broker.modify_order.assert_any_await("t-1", stop_loss=2316.0)
    assert snap.sl_price == 2316.0
    engine._execute_close.assert_not_awaited()
