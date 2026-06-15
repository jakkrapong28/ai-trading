"""Yahoo Finance provider — free REAL stock prices, no API key.

TwelveData/Finnhub free tiers don't stream US stocks (WS rejects them), so
without a paid plan the stocks fell back to mock. Yahoo's public chart endpoint
returns real prices with no key — the *same source the candles bootstrap from* —
so polling it gives live stock ticks on the correct scale.

Sits below the real-time WS feeds (TwelveData/Finnhub/MT5) and above the mock
gap-filler: it only emits when no higher-priority real feed is fresh.
"""
import asyncio
import logging
import os
from typing import Optional

import httpx

from backend.engines.providers.base import (
    MarketDataProvider,
    emit_tick,
    price_age,
    latest_prices,
    STALE_GAP_SECONDS,
)

logger = logging.getLogger("market-data.yahoo")

# Internal ticker -> Yahoo symbol. US stocks map 1:1; gold uses the GC=F
# futures chart (the same symbol the candles bootstrap from in candle_manager),
# so XAUUSD gets a real free price instead of falling through to the mock feed
# (TwelveData's free WS rejects XAU/USD, leaving mock as the only gold source).
YAHOO_SYMBOLS = {
    "AAPL": "AAPL", "NVDA": "NVDA", "TSLA": "TSLA", "MSFT": "MSFT", "AMZN": "AMZN",
    "XAUUSD": "GC=F",
}
HALF_SPREAD = 0.0005  # synthesize bid/ask around the real price
POLL_SECONDS = float(os.getenv("YAHOO_POLL_SECONDS", "12"))

# A higher-priority real feed for the same symbol means don't override with the
# (slightly more delayed) Yahoo poll.
_HIGHER_PRIORITY = {"twelvedata", "finnhub", "mt5", "binance"}


def parse_chart_price(payload: dict) -> Optional[float]:
    """Pull the latest price from a Yahoo v8 chart response (pure — testable)."""
    try:
        meta = payload["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        if price is None:
            price = meta.get("previousClose")  # fallback when market closed
        return float(price) if price is not None else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


class YahooProvider(MarketDataProvider):
    name = "yahoo"

    @property
    def enabled(self) -> bool:
        return True  # no key required

    async def _fetch_price(self, client: httpx.AsyncClient, ysym: str) -> Optional[float]:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
            "?interval=1m&range=1d"
        )
        try:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                logger.warning(f"Yahoo HTTP {r.status_code} for {ysym}")
                return None
            return parse_chart_price(r.json())
        except Exception as e:
            logger.warning(f"Yahoo fetch error for {ysym}: {e}")
            return None

    async def stream(self) -> None:
        logger.info(f"Yahoo provider active for {list(YAHOO_SYMBOLS)} (no key, real prices).")
        async with httpx.AsyncClient(timeout=10.0) as client:
            while True:
                try:
                    for ticker, ysym in YAHOO_SYMBOLS.items():
                        data = latest_prices.get(ticker)
                        if (
                            data
                            and data.get("source") in _HIGHER_PRIORITY
                            and price_age(ticker) <= STALE_GAP_SECONDS
                        ):
                            continue  # a true real-time WS feed is live — yield to it

                        price = await self._fetch_price(client, ysym)
                        if price and price > 0:
                            await emit_tick(
                                self.event_bus,
                                ticker=ticker,
                                price=price,
                                bid=price * (1 - HALF_SPREAD),
                                ask=price * (1 + HALF_SPREAD),
                                volume=0.0,
                                source="yahoo",
                            )
                        await asyncio.sleep(0.4)  # gentle pacing between symbols
                    await asyncio.sleep(POLL_SECONDS)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Yahoo provider loop error: {e}")
                    await asyncio.sleep(POLL_SECONDS)
