"""MT5 bridge provider — polls an HTTP bridge running MetaTrader5 on Windows.

The `MetaTrader5` Python package is Windows-only (it talks to a running MT5
terminal over IPC), so it cannot run on this macOS/Linux backend directly.
Instead, run `tools/mt5_bridge_server.py` on a Windows VPS with MT5 installed;
it exposes GET /ticks?symbols=... and this provider polls it.

Disabled silently when MT5_BRIDGE_URL is not set, so it is safe to leave in
the provider chain until a VPS is wired up.
"""
import asyncio
import logging
import os

import httpx

from backend.engines.providers.base import MarketDataProvider, emit_tick

logger = logging.getLogger("market-data.mt5")

POLL_INTERVAL = float(os.getenv("MT5_BRIDGE_POLL_SECONDS", "1.0"))
# Symbols to request from MT5 (broker-side metals/forex are most reliable here).
MT5_SYMBOLS = ["XAUUSD", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"]


class MT5BridgeProvider(MarketDataProvider):
    name = "mt5_bridge"

    def __init__(self, event_bus):
        super().__init__(event_bus)
        self.bridge_url = os.getenv("MT5_BRIDGE_URL", "").rstrip("/")
        self.api_key = os.getenv("MT5_BRIDGE_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.bridge_url)

    async def stream(self) -> None:
        if not self.enabled:
            logger.info("MT5_BRIDGE_URL not set — MT5 bridge provider disabled.")
            return

        url = f"{self.bridge_url}/ticks"
        params = {"symbols": ",".join(MT5_SYMBOLS)}
        headers = {"X-API-Key": self.api_key} if self.api_key else {}

        async with httpx.AsyncClient(timeout=8.0) as client:
            while True:
                try:
                    r = await client.get(url, params=params, headers=headers)
                    r.raise_for_status()
                    for t in r.json().get("ticks", []):
                        bid = float(t["bid"])
                        ask = float(t["ask"])
                        last = float(t.get("last") or (bid + ask) / 2)
                        await emit_tick(
                            self.event_bus,
                            ticker=t["symbol"],
                            price=last,
                            bid=bid,
                            ask=ask,
                            volume=float(t.get("volume") or 0.0),
                            source="mt5",
                        )
                    await asyncio.sleep(POLL_INTERVAL)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"MT5 bridge poll error: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
