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
    "smc_strategy": False,        # Phase B.2 — รอ closed trades ≥ 50
    "kelly_sizing": False,        # Phase 3 (หลัง backtest validate)
    "mtf_strategy": True,         # Phase B.2 — เปิดแล้ว (is_candle_closed fixed)
    "session_filter": False,
    "d1_bias_lock": True,         # Phase B.2 — เปิดแล้ว (with pre-flight auto-disable)
    "confirmation_candle": False, # Phase B.2 — รอ SMC เปิดก่อน
    "claude_fallback": False,
}
