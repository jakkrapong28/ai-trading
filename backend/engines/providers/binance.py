"""Binance WebSocket provider — live crypto prices (primary for crypto)."""
import asyncio
import json
import logging

import websockets

from backend.engines.providers.base import MarketDataProvider, emit_tick

logger = logging.getLogger("market-data.binance")

CRYPTO_PAIRS = ["btcusdt", "ethusdt", "solusdt", "bnbusdt"]


class BinanceProvider(MarketDataProvider):
    name = "binance"

    async def stream(self) -> None:
        streams = "/".join(f"{pair}@ticker" for pair in CRYPTO_PAIRS)
        ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"

        while True:
            try:
                logger.info(f"Connecting to Binance WS: {ws_url}")
                async with websockets.connect(ws_url) as ws:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if "data" not in data:
                            continue
                        d = data["data"]
                        await emit_tick(
                            self.event_bus,
                            ticker=d["s"].upper(),
                            price=float(d["c"]),
                            bid=float(d["b"]),
                            ask=float(d["a"]),
                            volume=float(d["v"]),
                            source="binance",
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Binance WS error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
