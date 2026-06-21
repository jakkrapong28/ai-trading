import os

ALERT_CHANNELS = {
    "telegram": {
        "enabled": True,
        "token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_CHAT_ID",
    },
    "line": {
        "enabled": False,  # LINE Notify is discontinued since 2025
        "token_env": "LINE_CHANNEL_ACCESS_TOKEN",
    },
}

CALIBRATION_TRIGGER = {
    "min_trades": 20,
    "max_days": 7,
}

TRADING_DAY_RESET_TZ = "America/New_York"
DAILY_LOSS_RESET_HOUR_UTC = 22

# Account starting capital — single source of truth (was hardcoded 45750 in 4 places).
# Override via env STARTING_BALANCE. Account equity = STARTING_BALANCE + closed PnL.
STARTING_BALANCE = float(os.getenv("STARTING_BALANCE", "45750"))

# Display-only split of total equity across funding sources for the dashboard.
# NOT a real per-broker balance — purely cosmetic until real broker accounts exist.
ACCOUNT_DISPLAY_SPLITS = {
    "MT5": 0.55,
    "BINANCE": 0.27,
    "ONCHAIN_WALLET": 0.18,
}

# Broker commission charged on close, expressed as a fraction of the traded
# notional value (lot × contractSize × price). Deterministic — never random.
# Per asset class so crypto taker fees (~0.075%) differ from FX/metal spreads.
# Override a single class via env COMMISSION_RATE_<CLASS> (e.g. COMMISSION_RATE_CRYPTO).
COMMISSION_RATE = {
    "metal": float(os.getenv("COMMISSION_RATE_METAL", "0.00008")),
    "forex": float(os.getenv("COMMISSION_RATE_FOREX", "0.00005")),
    "crypto": float(os.getenv("COMMISSION_RATE_CRYPTO", "0.00075")),
    "stock": float(os.getenv("COMMISSION_RATE_STOCK", "0.00035")),
    "index": float(os.getenv("COMMISSION_RATE_INDEX", "0.00005")),
}

FEATURE_FLAGS = {
    "circuit_breaker_v2": True,
    "rr_filter": True,
    "partial_tp": False,
    "adaptive_trailing": True,
    "spread_filter": True,
    "emergency_stop": True,
    "alerting": True,
    "correlation_cap": True,      # Basic cap — active ตั้งแต่ Phase 1B
    "smc_strategy": True,         # Path A — paper auto-execute ด้วยสมอง SMC ที่ validate แล้ว
    "kelly_sizing": False,        # Phase 3 (หลัง backtest validate)
    "mtf_strategy": True,         # Phase B.2 — เปิดแล้ว (is_candle_closed fixed)
    "session_filter": False,
    "d1_bias_lock": True,         # Phase B.2 — เปิดแล้ว (with pre-flight auto-disable)
    "confirmation_candle": False, # Phase B.2 — รอ SMC เปิดก่อน
    "claude_fallback": False,
}

# H1 — adaptive take-profit: take-profit RR per market regime. Empty = disabled →
# the live engine keeps the fixed RR 2.0 (tp = 2×SL). Fill in a proven map (e.g.
# {"BULL": 2.5, "BEAR": 2.5, "SIDEWAYS": 1.2, "VOLATILE": 1.5}) only after a
# walk-forward A/B validates it (Roadmap ข้อ 3). Keeps live == backtest.
RR_BY_REGIME = {}

# H2 — session-quality gate: minimum get_session_boost required to take an entry
# (0 = off). London/NY overlap=1.1, London/NY=1.0, Asian=0.8, Sydney=0.7.
MIN_SESSION_BOOST = float(os.getenv("MIN_SESSION_BOOST", "0"))

# Live SMC tuning — keep the live engine == the validated walk-forward best config.
# ADX(20) chop-guard was proven to lift the OOS pass-ratio once windows aren't thin
# (SYSTEM_UPGRADE §16); min_tier="C" is the base v2 grade. RR_BY_REGIME stays empty
# (H1 adaptive-TP was only marginal, §18) so live keeps the fixed RR 2.0.
SMC_LIVE_MIN_TIER = os.getenv("SMC_LIVE_MIN_TIER", "C")
SMC_LIVE_MIN_ADX = float(os.getenv("SMC_LIVE_MIN_ADX", "20"))
