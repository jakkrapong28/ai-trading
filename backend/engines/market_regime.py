import asyncio
import logging
import numpy as np

from backend.shared.events.core import EventBus, CH_MARKET_DATA, CH_MARKET_REGIME
from backend.shared.schema.events import MarketTickEvent, MarketRegimeEvent

logger = logging.getLogger("market-regime-engine")

# State
ticker_prices = {} # {ticker: [prices]}

def calculate_regime(prices):
    if len(prices) < 20:
        return "SIDEWAYS_LOW_VOL", 0.0, 0.0
    
    # Calculate simple returns
    returns = np.diff(prices) / prices[:-1]
    
    # Volatility proxy (std dev of returns * sqrt of window size)
    volatility = float(np.std(returns) * np.sqrt(len(prices)))
    
    # Trend strength (total return over the window)
    trend = float((prices[-1] - prices[0]) / prices[0])
    
    # Define state based on trend
    if trend > 0.005:
        state = "BULL"
    elif trend < -0.005:
        state = "BEAR"
    else:
        state = "SIDEWAYS"
        
    # Define volatility state
    if volatility > 0.002: # Threshold for high vol in this window
        vol_state = "HIGH_VOL"
    else:
        vol_state = "LOW_VOL"
        
    return f"{state}_{vol_state}", volatility, trend

async def process_market_data(event_bus: EventBus):
    logger.info("Market Regime Engine listening to CH_MARKET_DATA...")
    async for msg in event_bus.subscribe(CH_MARKET_DATA):
        try:
            tick = MarketTickEvent(**msg)
            ticker = tick.ticker
            
            if ticker not in ticker_prices:
                ticker_prices[ticker] = []
            
            ticker_prices[ticker].append(tick.price)
            
            # Keep a rolling window of 100 ticks
            if len(ticker_prices[ticker]) > 100:
                ticker_prices[ticker].pop(0)
                
            # Publish regime every 50 ticks to avoid overwhelming the bus
            # Original bug kept len at 100 so it published every tick. Fix: use a counter.
            if not hasattr(process_market_data, "counters"):
                process_market_data.counters = {}
                
            if ticker not in process_market_data.counters:
                process_market_data.counters[ticker] = 0
                
            process_market_data.counters[ticker] += 1
                
            if len(ticker_prices[ticker]) >= 20 and process_market_data.counters[ticker] % 50 == 0:
                regime_name, vol, trend = calculate_regime(ticker_prices[ticker])
                event = MarketRegimeEvent(
                    regime=regime_name,
                    volatility_score=vol,
                    trend_strength=trend
                )
                await event_bus.publish(CH_MARKET_REGIME, event.model_dump())
                logger.info(f"Regime evaluated for {ticker}: {regime_name} (Vol: {vol:.4f}, Trend: {trend:.4f})")
        except Exception as e:
            logger.error(f"Error processing tick: {e}")

def start_market_regime_engine(event_bus: EventBus):
    asyncio.create_task(process_market_data(event_bus))
