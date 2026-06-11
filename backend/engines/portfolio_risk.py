import logging
import math
from datetime import datetime, timezone
from typing import Dict, Any, List
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus, StrategyStats
from backend.core import SYMBOLS

logger = logging.getLogger("portfolio-risk")

def get_strategy_stats(symbol: str, regime: str) -> Dict[str, Any]:
    """Retrieve strategy stats from database, falling back to defaults if not present."""
    db = SessionLocal()
    try:
        stats = db.query(StrategyStats).filter(
            StrategyStats.symbol == symbol,
            StrategyStats.regime == regime
        ).first()
        if stats and stats.total_trades >= 10:
            return {
                "win_rate": stats.win_rate,
                "avg_win": stats.avg_win,
                "avg_loss": stats.avg_loss,
                "total_trades": stats.total_trades
            }
    except Exception as e:
        logger.error(f"Error reading StrategyStats: {e}")
    finally:
        db.close()
        
    return {
        "win_rate": 0.50,
        "avg_win": 20.0,
        "avg_loss": -20.0,
        "total_trades": 0
    }

def calc_kelly_lot(symbol: str, regime: str, equity: float, atr: float, contract_size: float, live_trades_count: int) -> Dict[str, Any]:
    """Calculates dynamically sized lot using Kelly Criterion with smooth linear ramp."""
    stats = get_strategy_stats(symbol, regime)
    wr = stats["win_rate"]
    avg_w = stats["avg_win"]
    avg_l = abs(stats["avg_loss"])

    if avg_l < 0.01 or live_trades_count < 10:
        return {"lot": 0.01, "kelly_pct": 0.0, "mode": "fallback"}

    r = avg_w / max(avg_l, 0.01)
    kelly_raw = max(0.0, wr - ((1 - wr) / r))

    # Linear ramp from trade 1 — smooth, no step discontinuity
    kelly_cap = 0.10 + min(1.0, live_trades_count / 50.0) * 0.15
    kelly_pct = kelly_raw * kelly_cap
    
    stop_dist = max(atr * 2.0, 10.0)
    risk_dollars = kelly_pct * max(equity, 100.0)
    lot = risk_dollars / max(stop_dist * contract_size, 1.0)
    lot = max(0.01, min(lot, 10.0))

    return {
        "lot": round(lot, 2),
        "kelly_pct": round(kelly_pct, 4),
        "mode": "kelly"
    }

def check_portfolio_heat(symbol: str, proposed_lot: float, stop_loss_dist: float, account_balance: float) -> Tuple[bool, str]:
    """
    Ensures sector exposure limits (Crypto <= 15%, Stock <= 20%, Gold <= 30%)
    and total portfolio risk limit (<= 20% total equity) are respected.
    """
    db = SessionLocal()
    try:
        open_trades = db.query(Trade).filter(
            Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
        ).all()
        
        # Calculate current exposure per asset class
        spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
        asset_class = spec.get("assetClass", "metal")
        contract_size = spec.get("contractSize", 100)
        proposed_risk = proposed_lot * stop_loss_dist * contract_size
        
        exposure_by_class = {"crypto": 0.0, "stock": 0.0, "metal": 0.0, "forex": 0.0}
        total_risk = 0.0
        
        for t in open_trades:
            t_spec = SYMBOLS.get(t.ticker, SYMBOLS["XAUUSD"])
            t_class = t_spec.get("assetClass", "metal")
            t_contract = t_spec.get("contractSize", 100)
            t_sl_dist = abs(t.entry_price - t.sl_price) if t.entry_price and t.sl_price else 0.0
            t_risk = t.lot_size * t_sl_dist * t_contract
            
            exposure_by_class[t_class] = exposure_by_class.get(t_class, 0.0) + t_risk
            total_risk += t_risk
            
        # Add proposed risk
        exposure_by_class[asset_class] += proposed_risk
        total_risk += proposed_risk
        
        # Limits
        limits = {"crypto": 0.15, "stock": 0.20, "metal": 0.30, "forex": 1.0}
        limit_pct = limits.get(asset_class, 1.0)
        class_limit = account_balance * limit_pct
        
        if exposure_by_class[asset_class] > class_limit:
            return False, f"Proposed trade exceeds {asset_class} sector risk limit ({exposure_by_class[asset_class]:.2f} > {class_limit:.2f})"
            
        max_total = account_balance * 0.20
        if total_risk > max_total:
            return False, f"Proposed trade exceeds total portfolio risk limit of 20% ({total_risk:.2f} > {max_total:.2f})"
            
        return True, ""
    except Exception as e:
        logger.error(f"Error checking portfolio heat: {e}")
        return True, ""  # Pass on error
    finally:
        db.close()
