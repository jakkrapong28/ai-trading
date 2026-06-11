import asyncio
import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone

from backend.shared.events.core import EventBus, CH_MARKET_REGIME, CH_SIGNALS, CH_AI_JOURNAL, CH_NEWS
from backend.shared.schema.events import MarketRegimeEvent, SignalEvent, NewsSentimentEvent
from backend.engines.market_data import get_latest_price
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus

logger = logging.getLogger("strategy-engine")

class StrategyEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.current_regimes: Dict[str, MarketRegimeEvent] = {}
        self.latest_news: Dict[str, NewsSentimentEvent] = {}
        self.target_tickers = ["BTCUSDT", "ETHUSDT", "NVDA", "AAPL", "MSFT", "XAUUSD"]
        self.last_signal_time: Dict[str, datetime] = {}
        
    async def bootstrap_regimes(self):
        try:
            logger.info("Bootstrapping market regimes from Redis Stream...")
            raw_data = await self.event_bus.redis.xrevrange("stream:market:regime:current", "+", "-", count=100)
            for msg_id, fields in reversed(raw_data):
                try:
                    msg = json.loads(fields["payload"])
                    event = MarketRegimeEvent(**msg)
                    self.current_regimes[event.ticker] = event
                except Exception:
                    pass
            logger.info(f"Bootstrapped regimes for: {list(self.current_regimes.keys())}")
        except Exception as e:
            logger.error(f"Error bootstrapping regimes: {e}")

    async def bootstrap_news(self):
        try:
            logger.info("Bootstrapping news sentiment from Redis Stream...")
            raw_data = await self.event_bus.redis.xrevrange("stream:news:sentiment", "+", "-", count=100)
            for msg_id, fields in reversed(raw_data):
                try:
                    msg = json.loads(fields["payload"])
                    event = NewsSentimentEvent(**msg)
                    self.latest_news[event.ticker] = event
                except Exception:
                    pass
            logger.info(f"Bootstrapped news for: {list(self.latest_news.keys())}")
        except Exception as e:
            logger.error(f"Error bootstrapping news: {e}")

    async def process_regime(self):
        await self.bootstrap_regimes()
        logger.info("Strategy Engine listening to CH_MARKET_REGIME...")
        async for msg in self.event_bus.subscribe_group(CH_MARKET_REGIME, "strategy_regime_group", "strategy_regime_worker_1"):
            try:
                event = MarketRegimeEvent(**msg)
                self.current_regimes[event.ticker] = event
            except Exception as e:
                logger.error(f"Error parsing regime event: {e}")

    async def process_news(self):
        await self.bootstrap_news()
        logger.info("Strategy Engine listening to CH_NEWS...")
        async for msg in self.event_bus.subscribe_group(CH_NEWS, "strategy_news_group", "strategy_news_worker_1"):
            try:
                event = NewsSentimentEvent(**msg)
                self.latest_news[event.ticker] = event
            except Exception as e:
                logger.error(f"Error parsing news event: {e}")

    def _has_open_trade(self, ticker: str) -> bool:
        db = SessionLocal()
        try:
            open_trade = db.query(Trade).filter(
                Trade.ticker == ticker,
                Trade.status.in_([TradeStatus.PENDING, TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
            ).first()
            return open_trade is not None
        except Exception as e:
            logger.error(f"Error checking open trades for {ticker}: {e}")
            return True # Safe default
        finally:
            db.close()

    async def evaluate_strategies(self):
        """Periodically evaluate conditions and generate signals."""
        while True:
            try:
                logger.info(f"[Strategy] Starting evaluation cycle. Regimes populated: {list(self.current_regimes.keys())}")
                for ticker in self.target_tickers:
                    # 1. Cooldown Check (15 mins)
                    now = datetime.now(timezone.utc)
                    last_time = self.last_signal_time.get(ticker)
                    if last_time and (now - last_time).total_seconds() < 900:
                        logger.debug(f"[Strategy] Skipping {ticker}: cooldown active.")
                        continue
                        
                    # 2. Prevent duplicate signals if open trade exists
                    has_open = await asyncio.to_thread(self._has_open_trade, ticker)
                    if has_open:
                        logger.debug(f"[Strategy] Skipping {ticker}: open trade exists.")
                        continue
                        
                    regime = self.current_regimes.get(ticker)
                    if not regime:
                        logger.debug(f"[Strategy] Skipping {ticker}: no regime data.")
                        continue
                        
                    news = self.latest_news.get(ticker)
                    news_score_val = news.final_news_score if news else 50.0 
                    
                    price_data = get_latest_price(ticker)
                    if not price_data:
                        logger.debug(f"[Strategy] Skipping {ticker}: no live price data or stale.")
                        continue
                        
                    # Calculate sub-scores (0 to 100)
                    trend_score = min(max((regime.trend_strength + 100) / 2.0, 0), 100)
                    momentum_score = trend_score
                    volume_score = 50.0
                    news_score = news_score_val
                    vol_score = min(regime.volatility_score, 100.0)
                    
                    # Multi-factor weighting
                    final_score = (
                        (trend_score * 0.30) +
                        (momentum_score * 0.25) +
                        (volume_score * 0.15) +
                        (news_score * 0.20) +
                        (vol_score * 0.10)
                    )
                    
                    logger.info(f"[Strategy] Evaluating {ticker}: final_score={final_score:.1f}, trend={trend_score:.1f}, news={news_score:.1f}, vol={vol_score:.1f}")
                    
                    signal_type = "HOLD"
                    if final_score >= 70:
                        signal_type = "BUY"
                    elif final_score <= 30:
                        signal_type = "SELL"
                        
                    if signal_type != "HOLD":
                        conf = abs(final_score - 50) / 50.0 
                        
                        breakdown = {
                            "trend": trend_score,
                            "momentum": momentum_score,
                            "volume": volume_score,
                            "news": news_score,
                            "volatility": vol_score,
                            "final": final_score
                        }
                        
                        reasoning = f"คะแนนวิเคราะห์ภาพรวม {final_score:.1f} กระตุ้นสัญญาณ {signal_type} | เทรนด์: {trend_score:.1f}, ข่าว: {news_score:.1f}"
                        
                        signal = SignalEvent(
                            ticker=ticker,
                            signal_type=signal_type,
                            probability=conf,
                            confidence_score=conf,
                            strategy_name="MultiFactorStrategy",
                            price_at_signal=price_data["last_price"],
                            atr=regime.atr,
                            score_breakdown=breakdown,
                            reasoning=reasoning
                        )
                        
                        self.last_signal_time[ticker] = now
                        await self.event_bus.publish(CH_SIGNALS, signal.model_dump())
                        logger.info(f"Generated {signal_type} signal for {ticker} (Score: {final_score:.1f})")
                        
                        journal_entry = {
                            "ticker": ticker,
                            "decision": "SIGNAL_GENERATED",
                            "signal_action": signal_type,
                            "confidence_score": conf,
                            "market_regime": regime.regime,
                            "sentiment_score": news_score,
                            "volatility_state": vol_score,
                            "reasons": [reasoning]
                        }
                        await self.event_bus.publish(CH_AI_JOURNAL, journal_entry)
                
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Strategy evaluation error: {e}")
                await asyncio.sleep(10)

def start_strategy_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    engine = StrategyEngine(event_bus)
    registry.register(engine.process_regime(), name="strategy_process_regime")
    registry.register(engine.process_news(), name="strategy_process_news")
    registry.register(engine.evaluate_strategies(), name="strategy_evaluate")
