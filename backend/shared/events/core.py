import json
import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class EventBus:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)

    async def publish(self, channel: str, message: dict):
        """Publish a JSON message to a Redis channel."""
        await self.redis.publish(channel, json.dumps(message))

    async def subscribe(self, channel: str):
        """Subscribe to a Redis channel and yield messages."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def close(self):
        await self.redis.close()

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
