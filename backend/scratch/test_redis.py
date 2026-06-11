import asyncio
import json
import redis.asyncio as redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def main():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    stream_key = "stream:market:tick"
    
    # Check length
    length = await r.xlen(stream_key)
    print("Stream length:", length)
    
    # Test xrevrange
    ticks = await r.xrevrange(stream_key, "+", "-", count=5)
    print("Xrevrange output (latest 5):")
    for t in ticks:
        print(t[0], t[1].keys())
        
    await r.close()

if __name__ == "__main__":
    asyncio.run(main())
