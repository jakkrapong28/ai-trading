import asyncio
import json
import websockets
import os

CRYPTO_PAIRS = ["btcusdt", "ethusdt", "solusdt", "bnbusdt"]
STOCK_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "XAUUSD"]
FINNHUB_API_KEY = "d7uc80pr01qnv95n28f0d7uc80pr01qnv95n28fg"

async def test_binance():
    streams = "/".join([f"{pair}@ticker" for pair in CRYPTO_PAIRS])
    ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    print(f"Connecting to Binance: {ws_url}...")
    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected to Binance successfully! Waiting for a message...")
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print("Received from Binance:", msg[:200])
            return True
    except Exception as e:
        print(f"Binance failed: {e}")
        return False

async def test_finnhub():
    ws_url = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    print(f"Connecting to Finnhub: {ws_url}...")
    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected to Finnhub successfully! Subscribing and waiting...")
            await ws.send(json.dumps({"type": "subscribe", "symbol": "AAPL"}))
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print("Received from Finnhub:", msg[:200])
            return True
    except Exception as e:
        print(f"Finnhub failed: {e}")
        return False

async def main():
    print("Testing WebSockets...")
    binance_ok = await test_binance()
    finnhub_ok = await test_finnhub()
    print(f"\nSummary:\nBinance WS: {'UP' if binance_ok else 'DOWN'}\nFinnhub WS: {'UP' if finnhub_ok else 'DOWN'}")

if __name__ == "__main__":
    asyncio.run(main())
