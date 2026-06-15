"""Market Data Engine — multi-source router with automatic failover.

Architecture (see engines/providers/):
  crypto (BTC/ETH/SOL/BNB) -> Binance spot WS                    -> mock gap-filler
  stock  (AAPL/NVDA/...)    -> TwelveData -> Finnhub -> Yahoo poll -> mock
  metal  (XAUUSD)           -> Binance futures WS (XAUUSDT perp) -> Yahoo poll (GC=F) -> mock

All real providers run concurrently and write through the single `emit_tick`
path. The mock provider only fills gaps for symbols whose real feed has gone
stale, so live data is never overwritten. A heartbeat task logs staleness and
which source is currently feeding each symbol.

Public API preserved for existing importers:
  start_market_data_engine(event_bus), latest_prices, get_latest_price
"""
import asyncio
import logging
from datetime import datetime, timezone

from backend.shared.events.core import EventBus
from backend.shared.tasks import registry

# Re-export the shared cache/helpers so existing imports keep working:
#   from backend.engines.market_data import latest_prices, get_latest_price
from backend.engines.providers.base import (  # noqa: F401
    latest_prices,
    get_latest_price,
    price_age,
    feed_status,
)
from backend.engines.providers import (
    BinanceProvider,
    BinanceGoldProvider,
    TwelveDataProvider,
    FinnhubProvider,
    MT5BridgeProvider,
    YahooProvider,
    MockProvider,
)

logger = logging.getLogger("market-data-service")

# Symbols whose freshness we report in the heartbeat.
MONITORED = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
             "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "XAUUSD"]


async def heartbeat_monitor():
    """Log per-symbol freshness and active source every 30s, and alert when a
    feed goes critically stale (>120s) so a dead provider isn't silent.

    Alerts are edge-triggered per symbol (fire once on entering STALE, reset on
    recovery) to avoid flooding the alert channel every 30s.
    """
    from backend.alert import send_alert
    stale_alerted: set = set()
    while True:
        try:
            await asyncio.sleep(30)
            for ticker in MONITORED:
                data = latest_prices.get(ticker)
                if not data:
                    logger.warning(f"[HEARTBEAT] {ticker} has no data yet.")
                    continue
                age = (datetime.now(timezone.utc) - data["timestamp"]).total_seconds()
                src = data.get("source", "?")
                if age > 120:
                    logger.warning(f"[HEARTBEAT] {ticker} STALE {age:.0f}s (last src={src})")
                    if ticker not in stale_alerted:
                        stale_alerted.add(ticker)
                        await send_alert("ERROR", f"📡 Market data stale for {ticker}: {age:.0f}s (last src={src})")
                elif age > 60:
                    logger.warning(f"[HEARTBEAT] {ticker} STALE {age:.0f}s (last src={src})")
                else:
                    logger.debug(f"[HEARTBEAT] {ticker} OK {age:.1f}s (src={src})")
                    if ticker in stale_alerted:
                        stale_alerted.discard(ticker)
                        await send_alert("INFO", f"✅ Market data recovered for {ticker} ({src})")
        except asyncio.CancelledError:
            break


def start_market_data_engine(event_bus: EventBus):
    """Instantiate all providers and register their stream tasks.

    Disabled providers (missing API key / bridge URL) short-circuit inside
    their own stream() and exit cleanly, so registering them is harmless.
    """
    providers = [
        BinanceProvider(event_bus),
        BinanceGoldProvider(event_bus),
        TwelveDataProvider(event_bus),
        FinnhubProvider(event_bus),
        MT5BridgeProvider(event_bus),
        YahooProvider(event_bus),   # free real stock prices (no key) — above mock
        MockProvider(event_bus),
    ]

    active = [p.name for p in providers if p.enabled]
    logger.info(f"Market data providers active: {active}")

    for p in providers:
        registry.register(p.stream(), name=f"market_{p.name}")

    registry.register(heartbeat_monitor(), name="market_heartbeat")
