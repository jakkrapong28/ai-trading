import os
import httpx
import logging
from backend.config import ALERT_CHANNELS

logger = logging.getLogger("alert")

async def send_alert(level: str, message: str, context: dict = None):
    """Push alert (Telegram primary) + structured log"""
    extra = {"context": context or {}, "alert_level": level}
    if level in ("ERROR", "CRITICAL"):
        logger.error(f"[ALERT][{level}] {message}", extra=extra)
    else:
        logger.warning(f"[ALERT][{level}] {message}", extra=extra)

    # Telegram (primary)
    tg = ALERT_CHANNELS.get("telegram", {})
    if tg.get("enabled"):
        token = os.getenv(tg["token_env"])
        chat_id = os.getenv(tg["chat_id_env"])
        if token and chat_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": f"🚨 [{level}] {message}"},
                        timeout=3.0,
                    )
            except Exception as e:
                logger.error(f"Telegram alert failed: {e}")

    # LINE (optional — LINE OA + Channel Access Token)
    line = ALERT_CHANNELS.get("line", {})
    if line.get("enabled"):
        token = os.getenv(line["token_env"])
        user_id = os.getenv(line.get("chat_id_env", "LINE_USER_ID"))
        if token and user_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "https://api.line.me/v2/bot/message/push",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json={"to": user_id, "messages": [{"type": "text", "text": f"🚨 [{level}] {message}"}]},
                        timeout=3.0,
                    )
            except Exception as e:
                logger.error(f"LINE push failed: {e}")
