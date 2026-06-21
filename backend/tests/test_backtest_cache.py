"""Guard the pinned-dataset cache (2026-06-21).

`fetch_backtest_data` freezes the first fetch per (symbol, interval, range) to
disk so walk-forward backtests are reproducible — the same config no longer
swings ±several pp just because Yahoo returned a different bar count. These
tests pin: (1) save/load is byte-faithful, (2) filenames are filesystem-safe,
(3) a cache hit never touches the network, (4) BT_CACHE_REFRESH re-pins.
"""
import os
import asyncio

import pandas as pd
import pytest

import backend.backtest as bt


def _df(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": range(n), "high": range(n), "low": range(n),
        "close": range(n), "volume": range(n),
    })


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BT_DATA_CACHE", str(tmp_path))
    monkeypatch.delenv("BT_CACHE_REFRESH", raising=False)
    return tmp_path


def _patch_fetch(monkeypatch, df):
    """Replace the network fetch with a counting stub so tests are offline and
    can assert exactly how many times the wrapper hit the network."""
    calls = {"n": 0}

    async def fake(symbol, interval, range_val):
        calls["n"] += 1
        return df.copy()

    monkeypatch.setattr(bt, "_fetch_yahoo", fake)
    return calls


def test_save_load_roundtrip_identical(cache_dir):
    df = _df()
    base = bt._cache_base_path("GC=F", "1h", "730d")
    bt._save_cache(base, df)
    pd.testing.assert_frame_equal(df, bt._load_cache(base))


def test_filename_sanitized(cache_dir):
    base = bt._cache_base_path("GC=F", "1h", "730d")
    name = os.path.basename(base)
    assert "=" not in name and "/" not in name
    assert os.path.dirname(base) == str(cache_dir)


def test_second_call_hits_cache_no_network(cache_dir, monkeypatch):
    df = _df()
    calls = _patch_fetch(monkeypatch, df)
    first = asyncio.run(bt.fetch_backtest_data("GC=F", "1h", "730d"))
    second = asyncio.run(bt.fetch_backtest_data("GC=F", "1h", "730d"))
    assert calls["n"] == 1  # network only on the initial miss
    pd.testing.assert_frame_equal(first, second)


def test_refresh_env_refetches_and_overwrites(cache_dir, monkeypatch):
    calls = _patch_fetch(monkeypatch, _df())
    asyncio.run(bt.fetch_backtest_data("GC=F", "1h", "730d"))
    monkeypatch.setenv("BT_CACHE_REFRESH", "1")
    asyncio.run(bt.fetch_backtest_data("GC=F", "1h", "730d"))
    assert calls["n"] == 2  # refresh bypasses cache and re-pins
