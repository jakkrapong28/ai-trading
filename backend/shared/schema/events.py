from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class MarketTickEvent(BaseModel):
    ticker: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    timestamp: Optional[datetime] = None
    source: str

class NewsSentimentEvent(BaseModel):
    ticker: str
    headline: str
    sentiment_score: float
    relevance_score: float = 1.0
    recency_score: float = 1.0
    source_quality_score: float = 1.0
    final_news_score: float
    confidence_score: float
    source: str

class MarketRegimeEvent(BaseModel):
    ticker: str
    regime: str 
    volatility_score: float
    trend_strength: float
    atr: float

class SignalEvent(BaseModel):
    ticker: str
    signal_type: str 
    probability: float
    confidence_score: float
    strategy_name: str
    price_at_signal: float
    atr: float
    score_breakdown: Dict[str, float]
    reasoning: str

class RiskApprovedEvent(BaseModel):
    ticker: str
    action: str 
    lot_size: float
    signal_price: float
    stop_loss: float
    take_profit: float
    strategy_name: str
    atr_at_entry: float
    market_regime: Optional[str] = None

class RiskRejectedEvent(BaseModel):
    ticker: str
    action: str
    reason: str

class AIDecisionEvent(BaseModel):
    ticker: str
    action: str
    confidence: float
    votes: Dict[str, str]
    reasoning: str

class ExecutionEvent(BaseModel):
    trade_id: str
    ticker: str
    action: str
    status: str 
    lot_size: float
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    message: Optional[str] = None

class PortfolioSnapshotEvent(BaseModel):
    balance: float
    equity: float
    margin: float
    floating_pnl: float
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    drawdown: float
