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

FEATURE_FLAGS = {
    "circuit_breaker_v2": True,
    "rr_filter": True,
    "partial_tp": False,
    "adaptive_trailing": True,
    "spread_filter": True,
    "emergency_stop": True,
    "alerting": True,
    "correlation_cap": True,      # Basic cap — active ตั้งแต่ Phase 1B
    "smc_strategy": False,        # Phase 2
    "kelly_sizing": False,        # Phase 3 (หลัง backtest validate)
    "mtf_strategy": False,
    "session_filter": False,
    "d1_bias_lock": False,
    "confirmation_candle": False,
    "claude_fallback": False,
}
