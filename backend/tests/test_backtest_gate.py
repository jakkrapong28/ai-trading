"""P4-1 · Walk-forward validation gate logic (pure, no network).

Guards the decision rule used by `python backend/backtest.py validate` before a
FEATURE_FLAG is enabled or a deploy proceeds.
"""
from backend.backtest import (
    evaluate_walk_forward,
    WALK_FORWARD_PASS_CRITERIA as PC,
)


def _win():
    return {"oos_metrics": {"sharpe_ratio": 1.5, "profit_factor": 1.8,
                            "max_drawdown": 8.0, "risk_of_ruin": 0.01}}


def _loss():
    return {"oos_metrics": {"sharpe_ratio": 0.2, "profit_factor": 0.9,
                            "max_drawdown": 25.0, "risk_of_ruin": 0.20}}


def test_all_windows_pass_gate_passes():
    ev = evaluate_walk_forward([_win(), _win(), _win(), _win()])
    assert ev["passed_windows"] == 4
    assert ev["pass_ratio"] == 100.0
    assert ev["gate_pass"] is True


def test_below_ratio_fails_gate():
    # 1/4 pass = 25% < 60%
    ev = evaluate_walk_forward([_win(), _loss(), _loss(), _loss()])
    assert ev["pass_ratio"] == 25.0
    assert ev["gate_pass"] is False


def test_too_few_windows_never_passes():
    # 2/2 = 100% ratio but < min_windows (3) → cannot green-light
    ev = evaluate_walk_forward([_win(), _win()])
    assert ev["enough_windows"] is False
    assert ev["gate_pass"] is False


def test_exactly_at_threshold_passes():
    # 3/5 = 60% meets the >=60% bar with enough windows
    ev = evaluate_walk_forward([_win(), _win(), _win(), _loss(), _loss()])
    assert ev["pass_ratio"] == 60.0
    assert ev["gate_pass"] is True


def test_infinite_profit_factor_counts_as_pass():
    r = {"oos_metrics": {"sharpe_ratio": 2.0, "profit_factor": float("inf"),
                         "max_drawdown": 5.0, "risk_of_ruin": 0.0}}
    ev = evaluate_walk_forward([r, r, r])
    assert ev["gate_pass"] is True


def test_each_criterion_can_fail_a_window():
    for bad in ("sharpe_ratio", "profit_factor", "max_drawdown", "risk_of_ruin"):
        m = {"sharpe_ratio": 1.5, "profit_factor": 1.8, "max_drawdown": 8.0, "risk_of_ruin": 0.01}
        # push the one metric just past its limit
        m[bad] = (PC[bad] - 0.01) if bad in ("sharpe_ratio", "profit_factor") else (PC[bad] + 0.01)
        ev = evaluate_walk_forward([{"oos_metrics": m}])
        assert ev["passed_windows"] == 0, f"{bad} should fail the window"
