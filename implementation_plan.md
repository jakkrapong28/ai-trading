# Implementation Plan - Standard Candlesticks & SMC Integration

The goal of this change is to resolve the technical anomalies (such as micro-RSI values, narrow support-resistance zones, and misleading static confidence scores) by:
1. Transitioning indicator calculations to standard candlestick timeframes (e.g. M15, H1) instead of micro-ticks.
2. Integrating the Smart Money Concepts (SMC) and Multi-Timeframe (MTF) strategy as the primary trade/indicator evaluation model.

## User Review Required

> [!IMPORTANT]
> The system will now download real historical candlestick data from Yahoo Finance on startup to seed the candlestick cache, with an automatic in-memory mock fallback in case of no internet access. This ensures that the frontend and backend analysis are both aligned with real-world chart levels.

## Proposed Changes

### [Backend - FastAPI]

#### [MODIFY] [config.py](file:///c:/Users/akkar/ai-trading/backend/config.py)
- Enable the feature flags `smc_strategy`, `mtf_strategy`, `d1_bias_lock`, and `confirmation_candle` to `True`.

#### [MODIFY] [base.py](file:///c:/Users/akkar/ai-trading/backend/core/base.py)
- Implement `CandleManager` class:
  - Fetches historical M15, H1, H4, and D1 candles from Yahoo Finance on start/demand (with in-memory mock fallback).
  - Updates the active bar in real-time when new ticks are received from the WebSocket.
  - Keeps a rolling list of the last 200 candles.
- Expose global `candle_manager = CandleManager()`.
- Update `evaluate_strategy_rules` function to evaluate SMC rules (BOS, CHoCH, Order Block, FVG) when `smc_strategy` is active and `ohlc_df` is passed.

#### [MODIFY] [mtf.py](file:///c:/Users/akkar/ai-trading/backend/core/mtf.py)
- Refactor `is_candle_closed` to support standard timeframes correctly by checking if the current time is past the end of the candle period (e.g. `timestamp + duration <= now`), resolving timestamp convention mismatches.

#### [MODIFY] [market_regime.py](file:///c:/Users/akkar/ai-trading/backend/engines/market_regime.py)
- Feed incoming market tick data from the WebSocket to the `candle_manager` in real-time.

#### [MODIFY] [strategy.py](file:///c:/Users/akkar/ai-trading/backend/engines/strategy.py)
- Refactor `evaluate_strategies` loop to retrieve proper aggregated timeframes (M15, H1, H4, D1) from the `candle_manager` and evaluate rules using the unified `evaluate_strategy_rules` function.

#### [MODIFY] [main.py](file:///c:/Users/akkar/ai-trading/backend/main.py)
- Update `/analyze` command handler to retrieve H1 candles from `candle_manager` and pass them to `get_market_indicators` and `evaluate_strategy_rules`.
- Update `websocket_bridge` tick handler to do the same for real-time WebSocket dashboard broadcasts.

---

## Verification Plan

### Automated Tests
- Run backend unit tests to ensure that all indicator calculations, risk checks, and SMC components compile and evaluate correctly:
  ```powershell
  pytest backend/tests/
  ```

### Manual Verification
- Start the backend and frontend servers.
- Use the Telegram command `/analyze BTCUSDT` or visit the web app dashboard.
- Verify that RSI values are standard (typically 30-70), support and resistance zones are realistic macro levels, and signals are correctly identified as SMC with matching confidence scores.
