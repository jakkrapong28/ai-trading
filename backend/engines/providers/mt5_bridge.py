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
# Canonical symbol -> broker symbol on the MT5 terminal. Exness suffixes its
# instruments with "m" (XAUUSDm, BTCUSDm, ...); we request the broker name but
# re-emit ticks under the canonical name the rest of the system uses (XAUUSD).
# Override the suffix per broker via MT5_SYMBOL_SUFFIX (default "m").
SYMBOL_SUFFIX = os.getenv("MT5_SYMBOL_SUFFIX", "m")
CANONICAL_SYMBOLS = ["XAUUSD", "EURUSD"]
# broker symbol (sent to bridge)  ->  canonical symbol (emitted on the bus)
BROKER_TO_CANONICAL = {f"{s}{SYMBOL_SUFFIX}": s for s in CANONICAL_SYMBOLS}
MT5_SYMBOLS = list(BROKER_TO_CANONICAL.keys())


class MT5BridgeProvider(MarketDataProvider):
    name = "mt5_bridge"

    def __init__(self, event_bus):
        super().__init__(event_bus)
        # Default to the local bridge so the provider is live out of the box;
        # the bridge returns no ticks until the user connects an MT5 account.
        self.bridge_url = os.getenv("MT5_BRIDGE_URL", "http://localhost:8765").rstrip("/")
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
                        # Re-map the broker symbol (XAUUSDm) back to canonical (XAUUSD).
                        ticker = BROKER_TO_CANONICAL.get(t["symbol"], t["symbol"])
                        bid = float(t["bid"])
                        ask = float(t["ask"])
                        last = float(t.get("last") or (bid + ask) / 2)
                        await emit_tick(
                            self.event_bus,
                            ticker=ticker,
                            price=last,
                            bid=bid,
                            ask=ask,
                            volume=float(t.get("volume") or 0.0),
                            source="mt5",
                        )
                    await asyncio.sleep(POLL_INTERVAL)
                except asyncio.CancelledError:
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    # Bridge process not running yet — stay quiet, back off longer.
                    await asyncio.sleep(10)
                except Exception as e:
                    logger.error(f"MT5 bridge poll error: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
