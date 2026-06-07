import uuid
from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, Integer, JSON, Boolean
from sqlalchemy.orm import relationship
from backend.shared.database.core import Base
from datetime import datetime
import enum

class MarketRegime(enum.Enum):
    BULL_HIGH_VOL = "BULL_HIGH_VOL"
    BULL_LOW_VOL = "BULL_LOW_VOL"
    BEAR_HIGH_VOL = "BEAR_HIGH_VOL"
    BEAR_LOW_VOL = "BEAR_LOW_VOL"
    SIDEWAYS_HIGH_VOL = "SIDEWAYS_HIGH_VOL"
    SIDEWAYS_LOW_VOL = "SIDEWAYS_LOW_VOL"

class SignalAction(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class TradeAction(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class TradeStatus(enum.Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    OPEN = "OPEN"
    RUNNING = "RUNNING"
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    CLOSED = "CLOSED"
    FAILED = "FAILED"

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
    status = Column(Enum(TradeStatus), default=TradeStatus.CREATED)
    lot_size = Column(Float)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    realized_pnl = Column(Float, nullable=True)
    pnl_percentage = Column(Float, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    position = relationship("Position", back_populates="trades")

class AIDecisionJournal(Base):
    __tablename__ = "ai_decision_journal"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ticker = Column(String, index=True)
    decision = Column(String) # e.g., "APPROVED", "REJECTED", "HOLD"
    signal_action = Column(Enum(SignalAction))
    confidence_score = Column(Float)
    market_regime = Column(Enum(MarketRegime))
    sentiment_score = Column(Float)
    volatility_state = Column(Float)
    reasons = Column(JSON) # List of strings explaining the decision
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
    timeframe = Column(String) # e.g., '1m', '5m', '1h'
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
    sentiment_score = Column(Float) # -1.0 to 1.0
    confidence_score = Column(Float) # 0.0 to 1.0
