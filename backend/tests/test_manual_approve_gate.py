"""Manual-approve gate · the /api/approve endpoint blocks a click unless the
same check_trade_risk() rules pass (circuit breaker folded in). These tests
pin the semantics the endpoint relies on to decide blocked vs allowed."""
from backend.core import check_trade_risk

COMMON = dict(
    symbol="XAUUSD", action="BUY", price=2000.0, stop_distance=20.0,
    spread=2.0, take_profit=40.0, reject_threshold=3.0, risk_pct_limit=1.5,
    equity=45750.0, broker_spread=2.0,
)


def test_clean_trade_passes():
    r = check_trade_risk(lot=0.01, **COMMON)
    assert r["passed"] is True
    assert all(c["pass"] for c in r["checks"])


def test_circuit_breaker_blocks_even_if_otherwise_fine():
    r = check_trade_risk(lot=0.01, circuit_breaker_triggered=True, **COMMON)
    assert r["passed"] is False
    failed = [c["name"] for c in r["checks"] if not c["pass"]]
    assert any("Circuit Breaker" in n for n in failed)


def test_oversized_lot_exceeds_risk_pct():
    # 1.0 lot · 20 · 100 = $2000 risk = 4.37% of equity > 1.5% limit
    r = check_trade_risk(lot=1.0, **COMMON)
    assert r["passed"] is False
    assert r["riskPct"] > COMMON["risk_pct_limit"]
