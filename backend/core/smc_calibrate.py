import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import SMCSignalLog, StrategyStats, Trade
from backend.config import CALIBRATION_TRIGGER

logger = logging.getLogger("smc-calibrate")

async def should_calibrate() -> bool:
    """Returns True if calibration condition triggers are met."""
    db = SessionLocal()
    try:
        total = db.query(SMCSignalLog).filter(
            SMCSignalLog.actual_outcome != "PENDING"
        ).count()
        if total == 0:
            return False
            
        recent = db.query(SMCSignalLog).filter(
            SMCSignalLog.calibrated_at.isnot(None)
        ).order_by(SMCSignalLog.calibrated_at.desc()).first()
        
        days_since = (datetime.now(timezone.utc) - recent.calibrated_at.replace(tzinfo=timezone.utc)).days if recent and recent.calibrated_at else 999
        return total >= CALIBRATION_TRIGGER.get("min_trades", 20) or days_since >= CALIBRATION_TRIGGER.get("max_days", 7)
    except Exception as e:
        logger.error(f"Error checking calibration trigger: {e}")
        return False
    finally:
        db.close()

async def run_calibration():
    """Aggregates win rate outcomes and updates StrategyStats cached weights."""
    db = SessionLocal()
    try:
        # 1. Update outcome of SMCSignalLogs that are still pending
        # Match them against completed Trades using symbol/timestamp or trade outcomes
        pending_signals = db.query(SMCSignalLog).filter(SMCSignalLog.actual_outcome == "PENDING").all()
        for sig in pending_signals:
            # Look for completed trades around the same symbol and within 1 day of signal creation
            trade = db.query(Trade).filter(
                Trade.ticker == sig.symbol,
                Trade.opened_at >= sig.created_at - timedelta(days=1),
                Trade.opened_at <= sig.created_at + timedelta(days=1),
                Trade.status == "CLOSED"
            ).first()
            if trade:
                pnl = trade.realized_pnl or 0.0
                sig.actual_outcome = "WIN" if pnl > 0 else "LOSS"
                sig.calibrated_at = datetime.utcnow()
                
        db.commit()

        # 2. Group and aggregate outcomes
        groups = db.query(
            SMCSignalLog.symbol, SMCSignalLog.signal_type, SMCSignalLog.confidence,
            func.count().label("total"),
            func.sum(case((SMCSignalLog.actual_outcome == "WIN", 1), else_=0)).label("wins")
        ).filter(SMCSignalLog.actual_outcome != "PENDING").group_by(
            SMCSignalLog.symbol, SMCSignalLog.signal_type, SMCSignalLog.confidence
        ).all()

        for g in groups:
            win_rate = float(g.wins) / float(g.total) if g.total > 0 else 0.50
            
            # Update signal logs
            db.query(SMCSignalLog).filter(
                SMCSignalLog.symbol == g.symbol,
                SMCSignalLog.signal_type == g.signal_type,
                SMCSignalLog.confidence == g.confidence
            ).update({
                "calibrated_confidence": round(win_rate, 2),
                "calibrated_at": datetime.utcnow()
            })
            
            # Update StrategyStats (creating if not existing)
            # Standard default regimes: BULL, BEAR, SIDEWAYS, VOLATILE
            for regime in ["BULL", "BEAR", "SIDEWAYS", "VOLATILE"]:
                stats = db.query(StrategyStats).filter(
                    StrategyStats.symbol == g.symbol,
                    StrategyStats.regime == regime
                ).first()
                
                # Fetch completed trades for average win/loss calculation
                trades_pnl = db.query(Trade.realized_pnl).filter(
                    Trade.ticker == g.symbol,
                    Trade.market_regime == regime,
                    Trade.status == "CLOSED"
                ).all()
                
                wins_list = [t[0] for t in trades_pnl if t[0] and t[0] > 0]
                losses_list = [t[0] for t in trades_pnl if t[0] and t[0] < 0]
                
                avg_win = float(sum(wins_list)) / len(wins_list) if wins_list else 20.0
                avg_loss = float(sum(losses_list)) / len(losses_list) if losses_list else -20.0
                
                if stats:
                    stats.win_rate = win_rate
                    stats.avg_win = avg_win
                    stats.avg_loss = avg_loss
                    stats.total_trades = g.total
                    stats.updated_at = datetime.utcnow()
                else:
                    stats = StrategyStats(
                        symbol=g.symbol,
                        regime=regime,
                        win_rate=win_rate,
                        avg_win=avg_win,
                        avg_loss=avg_loss,
                        total_trades=g.total,
                        updated_at=datetime.utcnow()
                    )
                    db.add(stats)
                    
        db.commit()
        logger.info(f"✅ Rolling calibration complete: updated {len(groups)} signal groups")
    except Exception as e:
        db.rollback()
        logger.error(f"Error executing calibration: {e}")
    finally:
        db.close()
