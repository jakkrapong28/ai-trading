import json
import os
import asyncio
import logging
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
logger = logging.getLogger("event-bus")

class EventBus:
    def __init__(self):
        self.redis = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=10.0,
            socket_connect_timeout=5.0,
            retry_on_timeout=True
        )

    async def publish(self, channel: str, message: dict):
        """Publish a JSON message to a Redis channel."""
        try:
            await self.redis.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")

    async def subscribe(self, channel: str):
        """Subscribe to a Redis channel and yield messages with auto-reconnect."""
        while True:
            pubsub = None
            try:
                pubsub = self.redis.pubsub()
                await pubsub.subscribe(channel)
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        yield json.loads(message["data"])
            except Exception as e:
                logger.warning(
                    f"Redis event bus subscription disconnected on channel '{channel}' ({type(e).__name__}: {e}). "
                    "Attempting reconnect in 3 seconds..."
                )
                await asyncio.sleep(3)
            finally:
                if pubsub:
                    try:
                        await pubsub.unsubscribe(channel)
                        await pubsub.close()
                    except Exception:
                        pass

    async def close(self):
        try:
            await self.redis.close()
        except Exception:
            pass

# Event Channel Constants
CH_MARKET_DATA = "market:tick"
CH_MARKET_CANDLE = "market:candle:1m"
CH_NEWS = "news:sentiment"
CH_MARKET_REGIME = "market:regime:current"
CH_SIGNALS = "ai:signal:generated"
CH_AI_JOURNAL = "ai:journal:log"
CH_RISK_APPROVED = "risk:signal:approved"
CH_RISK_REJECTED = "risk:signal:rejected"
CH_EXEC_OPENED = "execution:trade:opened"
CH_EXEC_CLOSED = "execution:trade:closed"
CH_EXEC_FAILED = "execution:trade:failed"
CH_PORTFOLIO_UPDATED = "portfolio:metrics:updated"
