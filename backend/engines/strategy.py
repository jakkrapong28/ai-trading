import asyncio
import logging
from typing import Dict, Any

from backend.shared.events.core import EventBus, CH_MARKET_REGIME, CH_SIGNALS, CH_AI_JOURNAL, CH_NEWS
from backend.shared.schema.events import MarketRegimeEvent, SignalEvent, NewsSentimentEvent

logger = logging.getLogger("strategy-engine")

class StrategyEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.current_regimes: Dict[str, MarketRegimeEvent] = {}
        self.latest_news: Dict[str, NewsSentimentEvent] = {}
        self.target_tickers = ["BTCUSDT", "ETHUSDT", "NVDA", "AAPL", "MSFT", "XAUUSD"]
        
    async def process_regime(self):
        logger.info("Strategy Engine listening to CH_MARKET_REGIME...")
        async for msg in self.event_bus.subscribe(CH_MARKET_REGIME):
            event = MarketRegimeEvent(**msg)
            # Default to tracking the overall regime globally or per-ticker if provided
            # The regime engine currently publishes without ticker, let's treat it as a global regime for crypto and stocks
            self.current_regimes["GLOBAL"] = event

    async def process_news(self):
        logger.info("Strategy Engine listening to CH_NEWS...")
        async for msg in self.event_bus.subscribe(CH_NEWS):
            event = NewsSentimentEvent(**msg)
            self.latest_news[event.ticker] = event

    async def evaluate_strategies(self):
        """Periodically evaluate conditions and generate signals."""
        while True:
            try:
                global_regime = self.current_regimes.get("GLOBAL")
                if not global_regime:
                    await asyncio.sleep(10)
                    continue
                    
                for ticker in self.target_tickers:
                    news = self.latest_news.get(ticker)
                    sentiment = news.sentiment_score if news else 0.0
                    
                    # Simple heuristic strategy combining regime and sentiment
                    signal_type = "HOLD"
                    confidence = 0.5
                    
                    if global_regime.regime.startswith("BULL") and sentiment > 0.2:
                        signal_type = "BUY"
                        confidence = 0.6 + (sentiment * 0.4)
                    elif global_regime.regime.startswith("BEAR") and sentiment < -0.2:
                        signal_type = "SELL"
                        confidence = 0.6 + (abs(sentiment) * 0.4)
                        
                    if signal_type != "HOLD" and confidence > 0.65:
                        signal = SignalEvent(
                            ticker=ticker,
                            signal_type=signal_type,
                            probability=confidence,
                            confidence_score=confidence,
                            strategy_name="RegimeSentimentAlpha",
                            price_at_signal=0.0 # Placeholder, ideally we have latest price
                        )
                        await self.event_bus.publish(CH_SIGNALS, signal.model_dump())
                        logger.info(f"Generated {signal_type} signal for {ticker} (Confidence: {confidence:.2f})")
                        
                        # Log to Journal
                        journal_entry = {
                            "ticker": ticker,
                            "decision": "SIGNAL_GENERATED",
                            "signal_action": signal_type,
                            "confidence_score": confidence,
                            "market_regime": global_regime.regime,
                            "sentiment_score": sentiment,
                            "reasons": [
                                f"Regime is {global_regime.regime}",
                                f"Sentiment score is {sentiment:.2f}"
                            ]
                        }
                        await self.event_bus.publish(CH_AI_JOURNAL, journal_entry)
                
                await asyncio.sleep(60) # Evaluate every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Strategy evaluation error: {e}")
                await asyncio.sleep(10)

def start_strategy_engine(event_bus: EventBus):
    engine = StrategyEngine(event_bus)
    asyncio.create_task(engine.process_regime())
    asyncio.create_task(engine.process_news())
    asyncio.create_task(engine.evaluate_strategies())
