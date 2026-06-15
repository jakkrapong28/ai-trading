"""Binance providers — live crypto (spot WS) + gold (XAUUSDT perp, REST poll)."""
import asyncio
import json
import logging
import os

import httpx
import websockets

from backend.engines.providers.base import MarketDataProvider, emit_tick

logger = logging.getLogger("market-data.binance")

CRYPTO_PAIRS = ["btcusdt", "ethusdt", "solusdt", "bnbusdt"]

# Gold trades as a USDT-margined perp (XAUUSDT) on Binance FUTURES — there is no
# spot gold pair, and the futures WebSocket (fstream) is unreliable / geo-blocked
# from some networks, so we REST-poll the futures ticker instead. Synthesize a
# tight book around the last price (the futures ticker has no bid/ask).
BINANCE_GOLD_REST = "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=XAUUSDT"
GOLD_POLL_SECONDS = float(os.getenv("BINANCE_GOLD_POLL_SECONDS", "5"))
HALF_SPREAD = 0.0002  # 2 bps


class BinanceProvider(MarketDataProvider):
    """Crypto spot ticks over Binance WebSocket (primary crypto feed)."""

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


class BinanceGoldProvider(MarketDataProvider):
    """XAUUSD via Binance's XAUUSDT perp, REST-polled (fstream WS is blocked).

    Emits source='binance' (a real feed) so XAUUSD stays off the mock gap-filler;
    Yahoo GC=F remains a lower-priority real fallback if this poll goes stale.
    """

    name = "binance_gold"

    async def stream(self) -> None:
        async with httpx.AsyncClient(timeout=8.0) as client:
            while True:
                try:
                    r = await client.get(BINANCE_GOLD_REST)
                    if r.status_code == 200:
                        d = r.json()
                        price = float(d["lastPrice"])
                        if price > 0:
                            await emit_tick(
                                self.event_bus,
                                ticker="XAUUSD",
                                price=price,
                                bid=price * (1 - HALF_SPREAD),
                                ask=price * (1 + HALF_SPREAD),
                                volume=float(d.get("volume") or 0.0),
                                source="binance",
                            )
                    else:
                        logger.warning(f"Binance gold HTTP {r.status_code}")
                    await asyncio.sleep(GOLD_POLL_SECONDS)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Binance gold poll error: {e}. Retrying...")
                    await asyncio.sleep(GOLD_POLL_SECONDS)
