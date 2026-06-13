import asyncio
import logging
import json
import websockets
import os
from datetime import datetime, timezone
from typing import Dict, Any

from backend.shared.events.core import EventBus, CH_MARKET_DATA
from backend.shared.schema.events import MarketTickEvent
from backend.core.candle_manager import candle_managers

logger = logging.getLogger("market-data-service")

CRYPTO_PAIRS = ["btcusdt", "ethusdt", "solusdt", "bnbusdt"]
STOCK_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "XAUUSD"]
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# In-memory cache
latest_prices: Dict[str, Dict[str, Any]] = {}

def get_latest_price(ticker: str) -> Dict[str, Any]:
    """Expose latest_prices[ticker] with stale check"""
    data = latest_prices.get(ticker)
    if not data:
        return None
    
    # Reject stale data > 60 seconds
    age = (datetime.now(timezone.utc) - data["timestamp"]).total_seconds()
    if age > 60:
        logger.warning(f"Stale market data for {ticker} (age: {age}s)")
        return None
    
    return data

async def heartbeat_monitor():
    """Market heartbeat monitor to check data freshness"""
    while True:
        await asyncio.sleep(30)
        now = datetime.now(timezone.utc)
        for ticker, data in list(latest_prices.items()):
            age = (now - data["timestamp"]).total_seconds()
            if age > 60:
                logger.warning(f"[HEARTBEAT] {ticker} market data is STALE (>60s). Last updated: {data['timestamp']}")
            else:
                logger.debug(f"[HEARTBEAT] {ticker} OK (age: {age:.1f}s)")

async def binance_ws_client(event_bus: EventBus):
    """Connect to Binance WebSocket and stream live crypto prices."""
    # using @ticker for combined trade info (price, bid, ask, volume)
    streams = "/".join([f"{pair}@ticker" for pair in CRYPTO_PAIRS])
    ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    
    while True:
        try:
            logger.info(f"Connecting to Binance WS: {ws_url}")
            async with websockets.connect(ws_url) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if "data" in data:
                        ticker_data = data["data"]
                        ticker = ticker_data["s"].upper()
                        price = float(ticker_data["c"]) # last price
                        bid = float(ticker_data["b"]) # best bid price
                        ask = float(ticker_data["a"]) # best ask price
                        volume = float(ticker_data["v"]) # base asset volume
                        
                        ts = datetime.now(timezone.utc)
                        latest_prices[ticker] = {
                            "bid": bid,
                            "ask": ask,
                            "last_price": price,
                            "volume": volume,
                            "timestamp": ts
                        }
                        
                        # Feed tick into CandleManager for OHLC aggregation
                        cm = candle_managers.get(ticker)
                        if cm:
                            cm.on_tick(price, volume, ts)

                        tick = MarketTickEvent(
                            ticker=ticker,
                            price=price,
                            bid=bid,
                            ask=ask,
                            volume=volume,
                            timestamp=ts,
                            source="binance"
                        )
                        await event_bus.publish(CH_MARKET_DATA, tick.model_dump())
                        
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Binance WS error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

async def finnhub_ws_client(event_bus: EventBus):
    """Connect to Finnhub WebSocket and stream live stock prices."""
    if not FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY not set. Using mock stocks generator.")
        from backend.shared.tasks import registry
        registry.register(mock_stocks_generator(event_bus), name="market_mock_stocks")
        return
        
    ws_url = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    
    while True:
        try:
            logger.info("Connecting to Finnhub WS...")
            async with websockets.connect(ws_url) as ws:
                for ticker in STOCK_TICKERS:
                    await ws.send(json.dumps({"type": "subscribe", "symbol": ticker}))
                    
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if data.get("type") == "trade":
                        for trade in data.get("data", []):
                            ticker = trade["s"]
                            price = float(trade["p"])
                            volume = float(trade["v"])
                            
                            ts = datetime.now(timezone.utc)
                            latest_prices[ticker] = {
                                "bid": price * 0.999,
                                "ask": price * 1.001,
                                "last_price": price,
                                "volume": volume,
                                "timestamp": ts
                            }
                            
                            # Feed tick into CandleManager for OHLC aggregation
                            cm = candle_managers.get(ticker)
                            if cm:
                                cm.on_tick(price, volume, ts)

                            tick = MarketTickEvent(
                                ticker=ticker,
                                price=price,
                                bid=price * 0.999,
                                ask=price * 1.001,
                                volume=volume,
                                timestamp=ts,
                                source="finnhub"
                            )
                            await event_bus.publish(CH_MARKET_DATA, tick.model_dump())
                            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Finnhub WS error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

async def mock_stocks_generator(event_bus: EventBus):
    """Fallback generator for stocks if API key missing"""
    bases = {"AAPL": 170.0, "NVDA": 850.0, "TSLA": 180.0, "MSFT": 420.0, "GOOGL": 140.0, "XAUUSD": 2350.0}
    import random
    while True:
        try:
            for ticker, base_price in bases.items():
                change = (random.random() - 0.5) * 2.0
                bases[ticker] += change
                price = bases[ticker]
                volume = random.uniform(10, 500)
                
                ts = datetime.now(timezone.utc)
                latest_prices[ticker] = {
                    "bid": price * 0.999,
                    "ask": price * 1.001,
                    "last_price": price,
                    "volume": volume,
                    "timestamp": ts
                }
                # Feed tick into CandleManager for OHLC aggregation
                cm = candle_managers.get(ticker)
                if cm:
                    cm.on_tick(price, volume, ts)

                tick = MarketTickEvent(
                    ticker=ticker,
                    price=price,
                    bid=price * 0.999,
                    ask=price * 1.001,
                    volume=volume,
                    timestamp=ts,
                    source="mock"
                )
                await event_bus.publish(CH_MARKET_DATA, tick.model_dump())
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            break

def start_market_data_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    registry.register(binance_ws_client(event_bus), name="market_binance_ws")
    registry.register(finnhub_ws_client(event_bus), name="market_finnhub_ws")
    registry.register(heartbeat_monitor(), name="market_heartbeat")
