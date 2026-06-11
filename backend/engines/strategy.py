import asyncio
import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone
import pandas as pd

from backend.shared.events.core import EventBus, CH_MARKET_REGIME, CH_SIGNALS, CH_AI_JOURNAL, CH_NEWS
from backend.shared.schema.events import MarketRegimeEvent, SignalEvent, NewsSentimentEvent
from backend.engines.market_data import get_latest_price
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus, SignalCooldown

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
            return True
        finally:
            db.close()

    def _is_cooldown_active(self, symbol: str, signal_type: str) -> bool:
        from backend.config import FEATURE_FLAGS
        from datetime import timedelta
        if not FEATURE_FLAGS.get("signal_cooldown", True):
            now = datetime.now(timezone.utc)
            last_time = self.last_signal_time.get(symbol)
            return last_time is not None and (now - last_time).total_seconds() < 900
            
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            cooldown = db.query(SignalCooldown).filter(
                SignalCooldown.symbol == symbol,
                SignalCooldown.signal_type == signal_type,
                SignalCooldown.cooldown_until > now
            ).first()
            return cooldown is not None
        except Exception as e:
            logger.error(f"Error checking cooldown in DB: {e}")
            return False
        finally:
            db.close()

    def _mark_signal_cooldown(self, symbol: str, signal_type: str, cooldown_minutes: int = 15):
        from backend.config import FEATURE_FLAGS
        from datetime import timedelta
        if not FEATURE_FLAGS.get("signal_cooldown", True):
            self.last_signal_time[symbol] = datetime.now(timezone.utc)
            return
            
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            until = now + timedelta(minutes=cooldown_minutes)
            
            cooldown = db.query(SignalCooldown).filter(
                SignalCooldown.symbol == symbol,
                SignalCooldown.signal_type == signal_type
            ).first()
            if cooldown:
                cooldown.cooldown_until = until
            else:
                cooldown = SignalCooldown(
                    symbol=symbol,
                    signal_type=signal_type,
                    cooldown_until=until
                )
                db.add(cooldown)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking cooldown in DB: {e}")
        finally:
            db.close()

    async def evaluate_strategies(self):
        """Periodically evaluate conditions and generate signals."""
        from backend.config import FEATURE_FLAGS
        while True:
            try:
                logger.info(f"[Strategy] Starting evaluation cycle. Regimes populated: {list(self.current_regimes.keys())}")
                for ticker in self.target_tickers:
                    # 1. Cooldown Check (15 mins)
                    if self._is_cooldown_active(ticker, "BUY") or self._is_cooldown_active(ticker, "SELL"):
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
                        
                    # 3. Retrieve tick history
                    from backend.engines.market_regime import ticker_data
                    df = ticker_data.get(ticker)
                    
                    signal_type = "HOLD"
                    conf = 0.0
                    reasoning = ""
                    breakdown = {}
                    
                    # 4. Evaluate using SMC/MTF if enabled
                    if FEATURE_FLAGS.get("smc_strategy", False) and df is not None and not df.empty:
                        from backend.core.smc import detect_smc_concepts, calculate_signal_confidence, get_session_boost
                        from backend.core.volume_profile import calculate_volume_profile
                        
                        atr = regime.atr
                        concepts = detect_smc_concepts(df, atr)
                        
                        # Evaluate Volume Profile
                        vp = calculate_volume_profile(df)
                        
                        d1_aligned = True
                        if FEATURE_FLAGS.get("mtf_strategy", False):
                            from backend.core.mtf import calculate_mtf_indicators, check_d1_bias_lock
                            # Build timeframe dataframes
                            ohlc_dict = {
                                "M15": df.rename(columns={"price": "close"}),
                                "H1": df.rename(columns={"price": "close"}),
                                "H4": df.rename(columns={"price": "close"}),
                                "D1": df.rename(columns={"price": "close"})
                            }
                            for tf, odf in ohlc_dict.items():
                                odf.index = pd.to_datetime(odf["timestamp"])
                            
                            mtf_data = calculate_mtf_indicators(ohlc_dict)
                            # Check lock for potential actions
                            d1_aligned = not check_d1_bias_lock(mtf_data, "BUY", atr) or not check_d1_bias_lock(mtf_data, "SELL", atr)
                        
                        concepts["d1_aligned"] = d1_aligned
                        conf = calculate_signal_confidence(concepts)
                        
                        if conf > 0.0:
                            # Session Boost
                            boost = get_session_boost(datetime.now(timezone.utc))
                            conf = min(1.0, conf * boost)
                            
                            # Determine action direction based on trend
                            action = "BUY" if regime.trend_strength > 0 else "SELL"
                            
                            # Confirmation Candle check
                            if FEATURE_FLAGS.get("confirmation_candle", True):
                                from backend.core import confirm_signal
                                ohlc_df = df.rename(columns={"price": "close"})
                                temp_sig = {"action": action, "confidence_score": conf, "price_at_signal": price_data["last_price"]}
                                if not confirm_signal(temp_sig, ohlc_df, atr):
                                    logger.info(f"[Strategy] {ticker} {action} signal pending confirmation candle. Skipping.")
                                    continue
                            
                            signal_type = action
                            reasoning = f"[SMC] {action} signal generated with confidence {conf:.2f}. POC: {vp['poc']:.2f}, VAH: {vp['vah']:.2f}"
                            breakdown = {
                                "trend": float(regime.trend_strength),
                                "momentum": float(regime.trend_strength),
                                "volume": float(vp["delta_volume"]),
                                "news": news_score_val,
                                "volatility": float(regime.volatility_score),
                                "final": conf * 100
                            }
                    else:
                        # Fallback: Multi-factor rule-based strategy
                        trend_score = min(max((regime.trend_strength + 100) / 2.0, 0), 100)
                        momentum_score = trend_score
                        volume_score = 50.0
                        news_score = news_score_val
                        vol_score = min(regime.volatility_score, 100.0)
                        
                        final_score = (
                            (trend_score * 0.30) +
                            (momentum_score * 0.25) +
                            (volume_score * 0.15) +
                            (news_score * 0.20) +
                            (vol_score * 0.10)
                        )
                        
                        if final_score >= 70:
                            signal_type = "BUY"
                        elif final_score <= 30:
                            signal_type = "SELL"
                            
                        if signal_type != "HOLD":
                            conf = abs(final_score - 50) / 50.0
                            reasoning = f"คะแนนวิเคราะห์ภาพรวม {final_score:.1f} กระตุ้นสัญญาณ {signal_type} | เทรนด์: {trend_score:.1f}, ข่าว: {news_score:.1f}"
                            breakdown = {
                                "trend": trend_score,
                                "momentum": momentum_score,
                                "volume": volume_score,
                                "news": news_score,
                                "volatility": vol_score,
                                "final": final_score
                            }
                            
                    if signal_type != "HOLD":
                        # Log signal to database if SMCSignalLog exists
                        db = SessionLocal()
                        try:
                            from backend.shared.database.models import SMCSignalLog
                            log_rec = SMCSignalLog(
                                symbol=ticker,
                                signal_type=signal_type,
                                confidence=conf,
                                actual_outcome="PENDING"
                            )
                            db.add(log_rec)
                            db.commit()
                        except Exception as log_err:
                            logger.error(f"Failed to log SMCSignalLog: {log_err}")
                        finally:
                            db.close()
                            
                        signal = SignalEvent(
                            ticker=ticker,
                            signal_type=signal_type,
                            probability=conf,
                            confidence_score=conf,
                            strategy_name="SMCStrategy" if FEATURE_FLAGS.get("smc_strategy", False) else "MultiFactorStrategy",
                            price_at_signal=price_data["last_price"],
                            atr=regime.atr,
                            score_breakdown=breakdown,
                            reasoning=reasoning
                        )
                        
                        self._mark_signal_cooldown(ticker, signal_type, cooldown_minutes=15)
                        await self.event_bus.publish(CH_SIGNALS, signal.model_dump())
                        logger.info(f"Generated {signal_type} signal for {ticker} (Confidence: {conf:.2f})")
                        
                        journal_entry = {
                            "ticker": ticker,
                            "decision": "SIGNAL_GENERATED",
                            "signal_action": signal_type,
                            "confidence_score": conf,
                            "market_regime": regime.regime,
                            "sentiment_score": news_score_val,
                            "volatility_state": regime.volatility_score,
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
