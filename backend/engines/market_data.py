import asyncio
import logging
import json
import websockets
import os
from dotenv import load_dotenv

from backend.shared.events.core import EventBus, CH_MARKET_DATA
from backend.shared.schema.events import MarketTickEvent

load_dotenv()
logger = logging.getLogger("market-data-service")

CRYPTO_PAIRS = ["btcusdt", "ethusdt", "solusdt", "bnbusdt"]
STOCK_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"]
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

async def binance_ws_client(event_bus: EventBus):
    """Connect to Binance WebSocket and stream live crypto prices."""
    streams = "/".join([f"{pair}@trade" for pair in CRYPTO_PAIRS])
    ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    
    while True:
        try:
            logger.info(f"Connecting to Binance WS: {ws_url}")
            async with websockets.connect(ws_url) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if "data" in data:
                        trade_data = data["data"]
                        ticker = trade_data["s"].upper()
                        price = float(trade_data["p"])
                        
                        tick = MarketTickEvent(
                            ticker=ticker,
                            price=price,
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
        logger.warning("FINNHUB_API_KEY not set. Skipping Finnhub WS.")
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
                            
                            tick = MarketTickEvent(
                                ticker=ticker,
                                price=price,
                                source="finnhub"
                            )
                            await event_bus.publish(CH_MARKET_DATA, tick.model_dump())
                            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Finnhub WS error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

def start_market_data_engine(event_bus: EventBus):
    asyncio.create_task(binance_ws_client(event_bus))
    asyncio.create_task(finnhub_ws_client(event_bus))
