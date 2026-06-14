"""Mock provider — last-resort gap filler.

Unlike the old unconditional mock generator, this only emits a synthetic tick
for a symbol when no real provider has updated it recently (price_age >
STALE_GAP_SECONDS). That way a live TwelveData/Finnhub/MT5 feed is never
overwritten by mock data, but the dashboard still shows moving prices when a
source is down or rate-limited.

BUG-1 fix: the mock used to random-walk from a HARD-CODED base (e.g. AAPL 190)
while the candle chart bootstraps real prices from Yahoo (e.g. AAPL ~290). The
two scales clashed inside one CandleManager — mock ticks crashed the Yahoo
candles, wrecking RSI/EMA/signals. The mock now seeds (and re-syncs) from the
real candle close so its ticks stay on the same scale as the chart.
"""
import asyncio
import logging
import random
from typing import Optional

from backend.engines.providers.base import (
    MarketDataProvider,
    emit_tick,
    price_age,
    STALE_GAP_SECONDS,
)
from backend.core.base import SYMBOLS
from backend.core.candle_manager import candle_managers

logger = logging.getLogger("market-data.mock")

# Final fallback seed used only when no candle data exists yet. Real price comes
# from the CandleManager (Yahoo bootstrap) via _candle_close().
BASES = {
    "AAPL": 190.0, "NVDA": 120.0, "TSLA": 180.0, "MSFT": 420.0,
    "AMZN": 185.0, "GOOGL": 140.0, "XAUUSD": 2350.0,
}
HALF_SPREAD = 0.001

# Symbols the mock fills for when their real feed is stale (stocks + metals).
# Crypto has Binance; forex has no synthetic feed (unchanged behaviour).
MOCK_SYMBOLS = [s for s, spec in SYMBOLS.items() if spec.get("assetClass") in ("stock", "metal")]


def _candle_close(ticker: str) -> Optional[float]:
    """Latest real candle close (Yahoo-bootstrapped) for `ticker`, or None."""
    cm = candle_managers.get(ticker)
    if cm is None:
        return None
    try:
        df = cm.get_ohlc("M15", bars=1)
        if df is not None and not df.empty:
            return float(df["close"].iloc[-1])
    except Exception:
        return None
    return None


def _resync_base(prev: Optional[float], candle_close: Optional[float], fallback: float) -> float:
    """Pick the price to random-walk from.

    - first tick: use the real candle close (else hard-coded fallback)
    - thereafter: keep the last mock price, but if it has drifted >5% from the
      real candle scale (e.g. stale 190 vs Yahoo 290), snap back to the candle.
    """
    if prev is None:
        return candle_close if candle_close else fallback
    if candle_close and abs(prev - candle_close) / candle_close > 0.05:
        return candle_close
    return prev


class MockProvider(MarketDataProvider):
    name = "mock"

    async def stream(self) -> None:
        from backend.engines.providers.base import latest_prices

        warned = False
        while True:
            try:
                for ticker in MOCK_SYMBOLS:
                    if price_age(ticker) <= STALE_GAP_SECONDS:
                        continue  # real feed is fresh — don't overwrite

                    if not warned:
                        logger.warning(
                            "Real feed stale/unavailable — mock gap-filler active "
                            "for stocks/metals."
                        )
                        warned = True

                    prev = latest_prices.get(ticker, {}).get("last_price")
                    candle_close = _candle_close(ticker)

                    # Don't emit a wrong-scale price before the Yahoo bootstrap
                    # has seeded candles — otherwise the first mock tick anchors
                    # to a stale base (190) and taints the real ~290 candles.
                    if prev is None and candle_close is None:
                        continue

                    base = _resync_base(prev, candle_close, BASES.get(ticker, 100.0))
                    if prev is not None and candle_close and base == candle_close and abs(prev - candle_close) / candle_close > 0.05:
                        logger.info(f"[mock] {ticker} resync {prev:.2f} → {candle_close:.2f} (real candle scale)")

                    # Random-walk relative to price so $290 and $2350 move sensibly.
                    step = max(0.05, base * 0.0008)
                    price = base + (random.random() - 0.5) * 2 * step
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
