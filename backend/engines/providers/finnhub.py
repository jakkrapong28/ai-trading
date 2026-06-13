"""Finnhub WebSocket provider — stocks (secondary, behind TwelveData).

Kept as a fallback. Note: Finnhub's free tier no longer streams US stock
trades in real time and has no XAUUSD, so this rarely produces data — it sits
in the chain below TwelveData and above the mock gap-filler.
"""
import asyncio
import json
import logging
import os

import websockets

from backend.engines.providers.base import MarketDataProvider, emit_tick

logger = logging.getLogger("market-data.finnhub")

STOCK_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"]
HALF_SPREAD = 0.001


class FinnhubProvider(MarketDataProvider):
    name = "finnhub"

    def __init__(self, event_bus):
        super().__init__(event_bus)
        self.api_key = os.getenv("FINNHUB_API_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def stream(self) -> None:
        if not self.enabled:
            logger.info("FINNHUB_API_KEY not set — Finnhub provider disabled.")
            return

        ws_url = f"wss://ws.finnhub.io?token={self.api_key}"

        while True:
            try:
                logger.info("Connecting to Finnhub WS...")
                async with websockets.connect(ws_url) as ws:
                    for ticker in STOCK_TICKERS:
                        await ws.send(json.dumps({"type": "subscribe", "symbol": ticker}))

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if data.get("type") != "trade":
                            continue
                        for trade in data.get("data", []):
                            price = float(trade["p"])
                            await emit_tick(
                                self.event_bus,
                                ticker=trade["s"],
                                price=price,
                                bid=price * (1 - HALF_SPREAD),
                                ask=price * (1 + HALF_SPREAD),
                                volume=float(trade.get("v", 0.0)),
                                source="finnhub",
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Finnhub WS error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
