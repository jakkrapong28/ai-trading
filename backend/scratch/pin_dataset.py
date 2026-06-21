"""Pre-warm the pinned backtest dataset (2026-06-21).

Fetches every research symbol once at 1h/730d so the bars are frozen to
backend/data/cache and every later walk-forward / A/B run replays the SAME
bars (reproducible across runs and machines). Commit the resulting cache
files so PC and Mac validate on identical data.

Usage:
  python backend/scratch/pin_dataset.py            # pin missing symbols
  BT_CACHE_REFRESH=1 python backend/scratch/pin_dataset.py   # re-pin (overwrite)
"""
import asyncio

from backend.backtest import fetch_backtest_data
from backend.core.base import YAHOO_SYMBOL_MAP

# The symbols the strategy research actually walk-forwards on (1h / 730d).
SYMBOLS = ["XAUUSD", "BTCUSDT", "ETHUSDT"]
INTERVAL, RANGE = "1h", "730d"


async def main():
    for sym in SYMBOLS:
        yf = YAHOO_SYMBOL_MAP.get(sym, sym)
        df = await fetch_backtest_data(yf, INTERVAL, RANGE)
        print(f"pinned {sym:<8} ({yf:<8}) {INTERVAL}/{RANGE}  bars={len(df)}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
