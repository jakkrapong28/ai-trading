import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque

import pandas as pd
import httpx

logger = logging.getLogger("candle_manager")

# Global registry of CandleManagers keyed by symbol (e.g. "XAUUSD")
candle_managers: Dict[str, "CandleManager"] = {}

TIMEFRAMES = {
    "M15": timedelta(minutes=15),
    "H1":  timedelta(hours=1),
    "H4":  timedelta(hours=4),
    "D1":  timedelta(days=1),
}

YAHOO_SYMBOL_MAP = {
    "XAUUSD": "GC=F", "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD",
    "SOLUSDT": "SOL-USD", "EURUSD": "EURUSD=X",
}

YAHOO_TIMEFRAME_MAP = {
    "M15": "15m",
    "H1": "1h",
    "H4": "1h",
    "D1": "1d",
}


def _floor_timestamp(ts: datetime, tf: str) -> datetime:
    """Floor a timestamp to the start of the candle period for the given timeframe."""
    if tf == "M15":
        return ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)
    elif tf == "H1":
        return ts.replace(minute=0, second=0, microsecond=0)
    elif tf == "H4":
        return ts.replace(hour=(ts.hour // 4) * 4, minute=0, second=0, microsecond=0)
    elif tf == "D1":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return ts


class CandleManager:
    """Aggregates tick data into real OHLC candles across multiple timeframes.

    Usage:
        cm = CandleManager("XAUUSD")
        cm.on_tick(price=2350.0, volume=100, timestamp=datetime.now(timezone.utc))
        df_h1 = cm.get_ohlc("H1", bars=50)
        all_tf = cm.get_all_timeframes()
    """

    def __init__(self, symbol: str, max_candles: int = 200):
        self.symbol = symbol
        self.max_candles = max_candles

        # Completed candles per timeframe: deque of dicts
        self._candles: Dict[str, deque] = {
            tf: deque(maxlen=max_candles) for tf in TIMEFRAMES
        }
        # Currently building candle per timeframe: {open, high, low, close, volume, timestamp, started_at}
        self._building: Dict[str, Optional[dict]] = {
            tf: None for tf in TIMEFRAMES
        }

    # ── Public API ──────────────────────────────────────────────

    def on_tick(self, price: float, volume: float, timestamp: datetime):
        """Feed a new tick into the candle manager.

        Must be called for every tick received from the market data engine.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        for tf in TIMEFRAMES:
            self._update_candle(tf, price, volume, timestamp)

    def get_ohlc(self, timeframe: str, bars: Optional[int] = None) -> pd.DataFrame:
        """Return OHLC DataFrame for a single timeframe.

        Includes the building (current incomplete) candle as the last row.
        """
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unknown timeframe: {timeframe}. Use: {list(TIMEFRAMES.keys())}")

        candles = list(self._candles[timeframe])
        building = self._building[timeframe]
        if building:
            candles.append(building)

        if bars is not None and bars > 0:
            candles = candles[-bars:]

        if not candles:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "timestamp"])

        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def get_all_timeframes(self, bars: Optional[int] = None) -> Dict[str, pd.DataFrame]:
        """Return OHLC DataFrames for all timeframes.

        This is the primary method used by the MTF strategy engine.
        """
        return {tf: self.get_ohlc(tf, bars) for tf in TIMEFRAMES}

    def get_completed_ohlc(self, timeframe: str, bars: Optional[int] = None) -> pd.DataFrame:
        """Return only completed candles (excludes the building candle)."""
        candles = list(self._candles[timeframe])
        if bars is not None and bars > 0:
            candles = candles[-bars:]
        if not candles:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "timestamp"])
        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    @property
    def last_price(self) -> Optional[float]:
        """Latest price from any timeframe's building candle."""
        for tf in reversed(list(TIMEFRAMES.keys())):
            b = self._building[tf]
            if b is not None:
                return b["close"]
        return None

    # ── Internal ────────────────────────────────────────────────

    def _update_candle(self, tf: str, price: float, volume: float, ts: datetime):
        """Update the building candle for a single timeframe."""
        period_start = _floor_timestamp(ts, tf)
        building = self._building[tf]

        if building is None:
            # First candle ever
            self._building[tf] = {
                "open": price, "high": price, "low": price,
                "close": price, "volume": volume,
                "timestamp": period_start,
                "started_at": period_start,
            }
            return

        if building["started_at"] < period_start:
            # Candle closed — move to completed and start new
            closed = {
                "open": building["open"],
                "high": building["high"],
                "low": building["low"],
                "close": building["close"],
                "volume": building["volume"],
                "timestamp": building["timestamp"],
            }
            self._candles[tf].append(closed)

            self._building[tf] = {
                "open": price, "high": price, "low": price,
                "close": price, "volume": volume,
                "timestamp": period_start,
                "started_at": period_start,
            }
        else:
            # Same candle period — update OHLC
            b = self._building[tf]
            b["high"] = max(b["high"], price)
            b["low"] = min(b["low"], price)
            b["close"] = price
            b["volume"] += volume

    # ── Yahoo Finance Bootstrap ─────────────────────────────────

    async def bootstrap_from_yahoo(self, force: bool = False):
        """Seed candle data from Yahoo Finance when no real ticks are available.

        Fetches data for each timeframe and populates both completed and building candles.
        This ensures the system has meaningful historical data from the start.
        """
        yahoo_symbol = YAHOO_SYMBOL_MAP.get(self.symbol, self.symbol)

        for tf, duration in TIMEFRAMES.items():
            if not force and len(self._candles[tf]) > 0:
                continue  # Already has data, skip

            yahoo_interval = YAHOO_TIMEFRAME_MAP.get(tf, "1h")
            range_val = "30d" if tf in ("M15", "H1") else "90d"
            if tf == "D1":
                range_val = "180d"

            try:
                df = await self._fetch_yahoo_ohlc(yahoo_symbol, yahoo_interval, range_val)
                if df is None or df.empty:
                    logger.warning(f"[{self.symbol}] Yahoo fetch returned empty for {tf}")
                    continue

                for _, row in df.iterrows():
                    candle = {
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row.get("volume", 0)),
                        "timestamp": row["timestamp"],
                    }
                    self._candles[tf].append(candle)

                logger.info(
                    f"[{self.symbol}] Bootstrapped {len(df)} {tf} candles from Yahoo Finance"
                )
            except Exception as e:
                logger.error(f"[{self.symbol}] Yahoo bootstrap failed for {tf}: {e}")

    async def _fetch_yahoo_ohlc(
        self, symbol: str, interval: str, range_val: str
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLC data from Yahoo Finance v8 chart API."""
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?interval={interval}&range={range_val}"
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, headers=headers)
                if r.status_code != 200:
                    logger.warning(f"Yahoo HTTP {r.status_code} for {symbol} {interval}")
                    return None

                result = r.json().get("chart", {}).get("result", [{}])[0]
                timestamps = result.get("timestamp", [])
                quote = result.get("indicators", {}).get("quote", [{}])[0]

                if not timestamps:
                    return None

                df = pd.DataFrame({
                    "timestamp": [datetime.fromtimestamp(t, tz=timezone.utc) for t in timestamps],
                    "open": quote.get("open", []),
                    "high": quote.get("high", []),
                    "low": quote.get("low", []),
                    "close": quote.get("close", []),
                    "volume": quote.get("volume", []),
                })
                return df.dropna().reset_index(drop=True)
        except Exception as e:
            logger.error(f"Yahoo fetch error for {symbol} {interval}: {e}")
            return None

    # ── Utility ─────────────────────────────────────────────────

    def status(self) -> dict:
        """Return status info about candle counts per timeframe."""
        return {
            tf: {
                "completed": len(self._candles[tf]),
                "building": self._building[tf] is not None,
                "last_close": self._candles[tf][-1]["close"] if self._candles[tf] else None,
            }
            for tf in TIMEFRAMES
        }

    def __repr__(self) -> str:
        counts = {tf: len(c) for tf, c in self._candles.items()}
        return f"CandleManager({self.symbol}, candles={counts})"
