"""Market data provider base + shared tick emission.

This module owns the global `latest_prices` cache and the single `emit_tick`
helper that every provider uses. Keeping this logic in one place removes the
duplication that previously lived in market_data.py (latest_prices update +
candle feed + event publish were copy-pasted across binance/finnhub/mock).
"""
import abc
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.shared.events.core import EventBus, CH_MARKET_DATA
from backend.shared.schema.events import MarketTickEvent
from backend.core.candle_manager import candle_managers

logger = logging.getLogger("market-data")

# In-memory cache of the latest tick per ticker. Source of truth for the
# whole market-data layer; imported by main.py, strategy, risk, portfolio.
latest_prices: Dict[str, Dict[str, Any]] = {}

# A tick older than this is considered stale (rejected by get_latest_price).
STALE_AFTER_SECONDS = 60
# Mock gap-filler only emits for a symbol whose real feed is older than this.
STALE_GAP_SECONDS = 30


def get_latest_price(ticker: str) -> Optional[Dict[str, Any]]:
    """Return latest_prices[ticker] or None if missing/stale (>60s)."""
    data = latest_prices.get(ticker)
    if not data:
        return None
    age = (datetime.now(timezone.utc) - data["timestamp"]).total_seconds()
    if age > STALE_AFTER_SECONDS:
        logger.warning(f"Stale market data for {ticker} (age: {age:.0f}s)")
        return None
    return data


def price_age(ticker: str) -> float:
    """Seconds since the last tick for `ticker` (inf if never seen)."""
    data = latest_prices.get(ticker)
    if not data:
        return float("inf")
    return (datetime.now(timezone.utc) - data["timestamp"]).total_seconds()


async def emit_tick(
    event_bus: EventBus,
    ticker: str,
    price: float,
    bid: float,
    ask: float,
    volume: float,
    source: str,
    timestamp: Optional[datetime] = None,
) -> None:
    """Single path for publishing a tick: update cache, feed candles, publish event.

    Every provider must go through here so behaviour stays consistent.
    """
    ts = timestamp or datetime.now(timezone.utc)

    latest_prices[ticker] = {
        "bid": bid,
        "ask": ask,
        "last_price": price,
        "volume": volume,
        "timestamp": ts,
        "source": source,
    }

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
        source=source,
    )
    await event_bus.publish(CH_MARKET_DATA, tick.model_dump())


class MarketDataProvider(abc.ABC):
    """A streaming source of market ticks.

    Subclasses run an infinite `stream()` loop and call `emit_tick(...)` for
    every quote. They should handle their own reconnect/backoff and respect
    asyncio.CancelledError for graceful shutdown.
    """

    name: str = "provider"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    @abc.abstractmethod
    async def stream(self) -> None:  # pragma: no cover - interface
        ...

    @property
    def enabled(self) -> bool:
        """Whether this provider has the config it needs to run."""
        return True
