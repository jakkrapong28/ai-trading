from pydantic import BaseModel
from typing import Optional, List

class MarketTickEvent(BaseModel):
    ticker: str
    price: float
    source: str

class NewsSentimentEvent(BaseModel):
    ticker: str
    headline: str
    sentiment_score: float
    confidence_score: float
    source: str

class MarketRegimeEvent(BaseModel):
    regime: str # e.g., "BULL_HIGH_VOL"
    volatility_score: float
    trend_strength: float

class SignalEvent(BaseModel):
    ticker: str
    signal_type: str # BUY, SELL, HOLD
    probability: float
    confidence_score: float
    strategy_name: str
    price_at_signal: float

class RiskApprovedEvent(BaseModel):
    ticker: str
    action: str # BUY, SELL
    lot_size: float
    signal_price: float
    stop_loss: float
    take_profit: float
    strategy_name: str

class RiskRejectedEvent(BaseModel):
    ticker: str
    action: str
    reason: str

class ExecutionEvent(BaseModel):
    trade_id: str
    ticker: str
    action: str
    status: str # OPEN, CLOSED, FAILED
    lot_size: float
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    message: Optional[str] = None
