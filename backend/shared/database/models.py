import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, Integer, JSON, Boolean
from sqlalchemy.orm import relationship
from backend.shared.database.core import Base

class MarketRegime(enum.Enum):
    BULL_HIGH_VOL = "BULL_HIGH_VOL"
    BULL_LOW_VOL = "BULL_LOW_VOL"
    BEAR_HIGH_VOL = "BEAR_HIGH_VOL"
    BEAR_LOW_VOL = "BEAR_LOW_VOL"
    SIDEWAYS_HIGH_VOL = "SIDEWAYS_HIGH_VOL"
    SIDEWAYS_LOW_VOL = "SIDEWAYS_LOW_VOL"
    VOLATILE_HIGH_VOL = "VOLATILE_HIGH_VOL"
    VOLATILE_LOW_VOL = "VOLATILE_LOW_VOL"
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    VOLATILE = "VOLATILE"

class SignalAction(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class TradeAction(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class TradeStatus(enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    current_exposure = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)
    trades = relationship("Trade", back_populates="position")

class Trade(Base):
    __tablename__ = "trades"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    position_id = Column(Integer, ForeignKey("positions.id"))
    ticker = Column(String, index=True)
    action = Column(Enum(TradeAction))
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)
    lot_size = Column(Float)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    sl_price = Column(Float, nullable=True)
    tp_price = Column(Float, nullable=True)
    atr_at_entry = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    votes = Column(JSON, nullable=True)
    realized_pnl = Column(Float, nullable=True)
    fee = Column(Float, nullable=True, default=0.0)
    pnl_percentage = Column(Float, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    highest_price = Column(Float, nullable=True)
    lowest_price = Column(Float, nullable=True)
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)
    trailing_notified = Column(Boolean, default=False)
    market_regime = Column(String, nullable=True)
    position = relationship("Position", back_populates="trades")

class AIDecisionJournal(Base):
    __tablename__ = "ai_decision_journal"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ticker = Column(String, index=True)
    decision = Column(String) 
    signal_action = Column(Enum(SignalAction))
    confidence_score = Column(Float)
    market_regime = Column(String) 
    sentiment_score = Column(Float)
    volatility_state = Column(Float)
    reasons = Column(JSON) 
    execution_result = Column(String, nullable=True)

class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    calculated_at = Column(DateTime, default=datetime.utcnow)

class MarketData(Base):
    __tablename__ = "market_data"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    timeframe = Column(String) 
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class NewsSentiment(Base):
    __tablename__ = "news_sentiment"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    headline = Column(String)
    source = Column(String)
    sentiment_score = Column(Float) 
    confidence_score = Column(Float) 

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    balance = Column(Float, default=0.0)
    equity = Column(Float, default=0.0)
    margin = Column(Float, default=0.0)
    floating_pnl = Column(Float, default=0.0)
    daily_pnl = Column(Float, default=0.0)
    weekly_pnl = Column(Float, default=0.0)
    monthly_pnl = Column(Float, default=0.0)
    drawdown = Column(Float, default=0.0)

class TradeLedger(Base):
    __tablename__ = "trade_ledger"
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String, ForeignKey("trades.id"))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String) 
    amount = Column(Float)
    description = Column(String)

class TaxLedger(Base):
    __tablename__ = "tax_ledger"
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String, ForeignKey("trades.id"))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    tax_type = Column(String) 
    amount = Column(Float)

class ERPDeliveryRecord(Base):
    __tablename__ = "erp_delivery_records"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trade_id = Column(String, index=True)
    idempotency_key = Column(String, index=True, unique=True)
    request_payload = Column(JSON)
    response_code = Column(Integer, nullable=True)
    response_body = Column(String, nullable=True)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

class SignalCooldown(Base):
    __tablename__ = "signal_cooldowns"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    signal_type = Column(String, index=True)
    cooldown_until = Column(DateTime, index=True)

class SMCSignalLog(Base):
    __tablename__ = "smc_signal_logs"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    signal_type = Column(String, index=True)
    confidence = Column(Float)
    calibrated_confidence = Column(Float, nullable=True)
    actual_outcome = Column(String, default="PENDING")
    calibrated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class StrategyStats(Base):
    __tablename__ = "strategy_stats"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    regime = Column(String, index=True)
    win_rate = Column(Float, default=0.5)
    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)
