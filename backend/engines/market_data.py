"""Market Data Engine — multi-source router with automatic failover.

Architecture (see engines/providers/):
  crypto (BTC/ETH/SOL/BNB) -> Binance WS                -> mock gap-filler
  stock  (AAPL/NVDA/...)    -> TwelveData -> Finnhub -> MT5 bridge -> mock
  metal  (XAUUSD)           -> TwelveData -> MT5 bridge          -> mock

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
)
from backend.engines.providers import (
    BinanceProvider,
    TwelveDataProvider,
    FinnhubProvider,
    MT5BridgeProvider,
    MockProvider,
)

logger = logging.getLogger("market-data-service")

# Symbols whose freshness we report in the heartbeat.
MONITORED = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
             "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "XAUUSD"]


async def heartbeat_monitor():
    """Log per-symbol freshness and active source every 30s."""
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
                if age > 60:
                    logger.warning(f"[HEARTBEAT] {ticker} STALE {age:.0f}s (last src={src})")
                else:
                    logger.debug(f"[HEARTBEAT] {ticker} OK {age:.1f}s (src={src})")
        except asyncio.CancelledError:
            break


def start_market_data_engine(event_bus: EventBus):
    """Instantiate all providers and register their stream tasks.

    Disabled providers (missing API key / bridge URL) short-circuit inside
    their own stream() and exit cleanly, so registering them is harmless.
    """
    providers = [
        BinanceProvider(event_bus),
        TwelveDataProvider(event_bus),
        FinnhubProvider(event_bus),
        MT5BridgeProvider(event_bus),
        MockProvider(event_bus),
    ]

    active = [p.name for p in providers if p.enabled]
    logger.info(f"Market data providers active: {active}")

    for p in providers:
        registry.register(p.stream(), name=f"market_{p.name}")

    registry.register(heartbeat_monitor(), name="market_heartbeat")
