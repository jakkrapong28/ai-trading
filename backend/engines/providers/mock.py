"""Mock provider — last-resort gap filler.

Unlike the old unconditional mock generator, this only emits a synthetic tick
for a symbol when no real provider has updated it recently (price_age >
STALE_GAP_SECONDS). That way a live TwelveData/Finnhub/MT5 feed is never
overwritten by mock data, but the dashboard still shows moving prices when a
source is down or rate-limited.
"""
import asyncio
import logging
import random

from backend.engines.providers.base import (
    MarketDataProvider,
    emit_tick,
    price_age,
    STALE_GAP_SECONDS,
)

logger = logging.getLogger("market-data.mock")

# Seed prices used only until a real source provides a value.
BASES = {
    "AAPL": 190.0, "NVDA": 120.0, "TSLA": 180.0, "MSFT": 420.0,
    "GOOGL": 140.0, "XAUUSD": 2350.0,
}
HALF_SPREAD = 0.001


class MockProvider(MarketDataProvider):
    name = "mock"

    async def stream(self) -> None:
        from backend.engines.providers.base import latest_prices

        warned = False
        while True:
            try:
                for ticker, seed in BASES.items():
                    if price_age(ticker) <= STALE_GAP_SECONDS:
                        continue  # real feed is fresh — don't overwrite

                    if not warned:
                        logger.warning(
                            "Real feed stale/unavailable — mock gap-filler active "
                            "for stocks/metals."
                        )
                        warned = True

                    # Random-walk from the last known price (real or mock).
                    last = latest_prices.get(ticker, {}).get("last_price", seed)
                    price = last + (random.random() - 0.5) * 2.0
                    await emit_tick(
                        self.event_bus,
                        ticker=ticker,
                        price=price,
                        bid=price * (1 - HALF_SPREAD),
                        ask=price * (1 + HALF_SPREAD),
                        volume=random.uniform(10, 500),
                        source="mock",
                    )
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Mock generator error: {e}")
                await asyncio.sleep(5)
