import asyncio
import logging
import json
import numpy as np
import pandas as pd
from typing import Dict, List

from backend.shared.events.core import EventBus, CH_MARKET_DATA, CH_MARKET_REGIME
from backend.shared.schema.events import MarketTickEvent, MarketRegimeEvent

logger = logging.getLogger("market-regime-engine")

# State
ticker_data: Dict[str, pd.DataFrame] = {} # Store recent history

def calculate_indicators(df: pd.DataFrame) -> dict:
    close = df['price']
    
    # EMA 50 and 200
    ema_50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    ema_200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    
    # MACD (12, 26, 9)
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = (macd - signal).iloc[-1]
    
    # ATR (14) proxy since we only have tick price (High=Low=Close)
    # We will use standard deviation of recent returns as a proxy for volatility/ATR for ticks
    returns = close.pct_change().dropna()
    atr_proxy = returns.rolling(window=14).std().iloc[-1] * close.iloc[-1] * np.sqrt(14)
    if pd.isna(atr_proxy):
        atr_proxy = 0.0

    return {
        "ema_50": ema_50,
        "ema_200": ema_200,
        "rsi": rsi if not pd.isna(rsi) else 50.0,
        "macd_hist": macd_hist if not pd.isna(macd_hist) else 0.0,
        "atr": atr_proxy
    }

def calculate_regime(df: pd.DataFrame):
    if len(df) < 200:
        return "SIDEWAYS", 0.0, 0.0, 0.0
    
    inds = calculate_indicators(df)
    price = df['price'].iloc[-1]
    
    ema_50 = inds["ema_50"]
    ema_200 = inds["ema_200"]
    rsi = inds["rsi"]
    macd_hist = inds["macd_hist"]
    atr = inds["atr"]
    
    # Trend Strength (0 to 100)
    trend_score = 0
    if price > ema_50: trend_score += 25
    if ema_50 > ema_200: trend_score += 25
    if macd_hist > 0: trend_score += 25
    if rsi > 50: trend_score += 25
    
    if price < ema_50: trend_score -= 25
    if ema_50 < ema_200: trend_score -= 25
    if macd_hist < 0: trend_score -= 25
    if rsi < 50: trend_score -= 25
    
    # Volatility Score
    # Normalize ATR relative to price
    vol_pct = (atr / price) if price > 0 else 0
    volatility_score = min(vol_pct * 10000, 100.0) # Arbitrary scaling for 0-100
    
    # Determine Regime
    if volatility_score > 70:
        regime = "VOLATILE"
    elif trend_score >= 50:
        regime = "BULL"
    elif trend_score <= -50:
        regime = "BEAR"
    else:
        regime = "SIDEWAYS"
        
    # Regime Score: Scale trend_score from -100..100 to 0..100
    regime_score = (trend_score + 100) / 2.0
    
    return regime, regime_score, float(trend_score), float(atr)

async def process_market_data(event_bus: EventBus):
    logger.info("Market Regime Engine listening to CH_MARKET_DATA...")
    counters = {}
    
    # Cold-start bootstrap: load last 1000 ticks from Redis Stream to populate historical data
    try:
        logger.info("Bootstrapping market regime historical data from Redis Stream...")
        raw_ticks = await event_bus.redis.xrevrange("stream:market:tick", "+", "-", count=1000)
        raw_ticks.reverse()
        for msg_id, fields in raw_ticks:
            try:
                msg = json.loads(fields["payload"])
                tick = MarketTickEvent(**msg)
                ticker = tick.ticker
                if ticker not in ticker_data:
                    ticker_data[ticker] = pd.DataFrame(columns=["timestamp", "price"])
                new_row = pd.DataFrame([{"timestamp": pd.to_datetime('now'), "price": tick.price}])
                ticker_data[ticker] = pd.concat([ticker_data[ticker], new_row], ignore_index=True)
                if len(ticker_data[ticker]) > 250:
                    ticker_data[ticker] = ticker_data[ticker].iloc[-250:].reset_index(drop=True)
                counters[ticker] = counters.get(ticker, 0) + 1
            except Exception as parse_err:
                logger.error(f"Error parsing tick in bootstrap: {parse_err}")
        logger.info(f"Bootstrapped historical data for: {list(ticker_data.keys())}. Tick counts: { {k: len(v) for k, v in ticker_data.items()} }")
    except Exception as bootstrap_err:
        logger.error(f"Error bootstrapping market regime: {bootstrap_err}")

    async for msg in event_bus.subscribe_group(CH_MARKET_DATA, "market_regime_group", "market_regime_worker_1"):
        try:
            tick = MarketTickEvent(**msg)
            ticker = tick.ticker
            
            if ticker not in ticker_data:
                ticker_data[ticker] = pd.DataFrame(columns=["timestamp", "price"])
            
            # Append new tick
            new_row = pd.DataFrame([{"timestamp": pd.to_datetime('now'), "price": tick.price}])
            ticker_data[ticker] = pd.concat([ticker_data[ticker], new_row], ignore_index=True)
            
            # Keep a rolling window of 250 ticks to calculate EMA 200
            if len(ticker_data[ticker]) > 250:
                ticker_data[ticker] = ticker_data[ticker].iloc[-250:].reset_index(drop=True)
                
            counters[ticker] = counters.get(ticker, 0) + 1
                
            # Evaluate regime every 50 ticks per ticker
            if len(ticker_data[ticker]) >= 200 and counters[ticker] % 50 == 0:
                regime_name, regime_score, trend, atr = calculate_regime(ticker_data[ticker])
                event = MarketRegimeEvent(
                    ticker=ticker,
                    regime=regime_name,
                    volatility_score=regime_score, 
                    trend_strength=trend,
                    atr=atr
                )
                await event_bus.publish(CH_MARKET_REGIME, event.model_dump())
                logger.info(f"Regime evaluated for {ticker}: {regime_name} (Trend: {trend:.1f}, ATR: {atr:.4f})")
        except Exception as e:
            logger.error(f"Error processing tick for regime: {e}")

def start_market_regime_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    registry.register(process_market_data(event_bus), name="market_regime_process")
