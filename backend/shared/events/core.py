import json
import os
import asyncio
import logging
import uuid
import contextvars
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
logger = logging.getLogger("event-bus")

correlation_id_ctx = contextvars.ContextVar('correlation_id', default='')

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
        """
        Publish using both Redis Streams (XADD) and Pub/Sub (publish) for backwards compatibility.
        """
        try:
            cid = correlation_id_ctx.get()
            if not cid:
                cid = str(uuid.uuid4())
                correlation_id_ctx.set(cid)
            
            message['_correlation_id'] = cid
            payload = json.dumps(message, default=str)
            
            # Redis Streams
            stream_key = f"stream:{channel}"
            await self.redis.xadd(stream_key, {"payload": payload})
            
            # Legacy Pub/Sub Adapter
            await self.redis.publish(channel, payload)
            
            logger.debug(f"[EventBus] Published to {channel} (CID: {cid})")
        except Exception as e:
            logger.error(f"[EventBus] Failed to publish to {channel}: {e}")
            await self.to_dlq(channel, message, str(e))

    async def subscribe(self, channel: str):
        """
        Legacy Pub/Sub subscriber (DEPRECATED - use subscribe_group instead)
        """
        while True:
            pubsub = None
            try:
                pubsub = self.redis.pubsub()
                await pubsub.subscribe(channel)
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            yield data
                        except Exception:
                            pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(3)
            finally:
                if pubsub:
                    try:
                        await pubsub.unsubscribe(channel)
                        await pubsub.close()
                    except Exception:
                        pass

    async def subscribe_group(self, channel: str, group_name: str, consumer_name: str):
        """
        Subscribe to a Redis Stream using Consumer Groups.
        Ensures reliable delivery, XACK, and XPENDING recovery.
        """
        stream_key = f"stream:{channel}"
        
        # Ensure group exists
        try:
            await self.redis.xgroup_create(stream_key, group_name, id='0', mkstream=True)
            logger.info(f"Created consumer group {group_name} for stream {stream_key}")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Error creating group: {e}")
                
        # Auto-claim pending messages that belong to dead consumers
        from backend.shared.tasks import registry
        registry.register(self._auto_claim_loop(stream_key, group_name, consumer_name), name=f"autoclaim_{group_name}")

        last_id = ">" # Read new messages
        
        while True:
            try:
                # First check for our own pending messages (0-0)
                if last_id == ">":
                    pending = await self.redis.xreadgroup(group_name, consumer_name, {stream_key: "0-0"}, count=100)
                    if pending and pending[0][1]:
                        last_id = "0-0"
                    else:
                        last_id = ">"

                messages = await self.redis.xreadgroup(
                    group_name, consumer_name, {stream_key: last_id}, count=10, block=2000
                )
                
                if not messages:
                    last_id = ">"
                    continue

                for _, msg_list in messages:
                    for msg_id, fields in msg_list:
                        try:
                            data = json.loads(fields["payload"])
                            cid = data.get('_correlation_id', '')
                            if cid:
                                correlation_id_ctx.set(cid)
                                
                            yield data
                            
                            # ACK the message
                            await self.redis.xack(stream_key, group_name, msg_id)
                        except Exception as parse_err:
                            logger.error(f"[EventBus] Parse error on {channel}: {parse_err}")
                            await self.to_dlq(channel, {"raw": fields.get("payload")}, str(parse_err))
                            await self.redis.xack(stream_key, group_name, msg_id) # Ack bad messages so they don't block
                            
                if last_id == "0-0":
                    last_id = ">" # Switch back to new messages after clearing backlog
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[EventBus] Stream disconnect on {channel}: {e}. Retrying in 3s...")
                await asyncio.sleep(3)

    async def _auto_claim_loop(self, stream_key: str, group_name: str, consumer_name: str):
        """Background task to reclaim abandoned messages (> 60s old)."""
        while True:
            try:
                # XAUTOCLAIM messages idle for > 60000ms (60s)
                # "0-0" is the start ID
                claimed = await self.redis.xautoclaim(stream_key, group_name, consumer_name, 60000, "0-0", count=50)
                
                if claimed and len(claimed) >= 2 and claimed[1]:
                    logger.info(f"[EventBus] {consumer_name} auto-claimed {len(claimed[1])} abandoned messages from {stream_key}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EventBus] Auto-claim failed for {stream_key}: {e}")
            await asyncio.sleep(30)

    async def to_dlq(self, channel: str, message: dict, error_reason: str):
        try:
            dlq_msg = {
                "original_channel": channel,
                "message": message,
                "error": error_reason,
                "timestamp": asyncio.get_event_loop().time()
            }
            await self.redis.lpush("dlq:events", json.dumps(dlq_msg, default=str))
            logger.warning(f"[EventBus] Message moved to DLQ (Channel: {channel})")
        except Exception as e:
            logger.error(f"[EventBus] Failed to push to DLQ: {e}")

    async def health_check(self) -> bool:
        try:
            return await self.redis.ping()
        except Exception:
            return False

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
CH_AI_DECISION = "ai:decision:final"
CH_EXEC_OPENED = "execution:trade:opened"
CH_EXEC_CLOSED = "execution:trade:closed"
CH_EXEC_FAILED = "execution:trade:failed"
CH_PORTFOLIO_UPDATED = "portfolio:metrics:updated"
CH_PORTFOLIO_SNAPSHOT = "portfolio:snapshot"
