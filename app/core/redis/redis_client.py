from typing import Optional
import redis.asyncio as aioredis
from core.settings import settings

_redis_client_instance: Optional[aioredis.Redis] = None

async def get_redis_client() -> aioredis.Redis:
    global _redis_client_instance
    if _redis_client_instance is None:
        _redis_client_instance = aioredis.Redis(
            host=settings.REDIS.HOST,
            port=settings.REDIS.PORT,
            db=settings.REDIS.DB,
            password=settings.REDIS.PASSWORD.get_secret_value(),
            decode_responses=True
        )
    return _redis_client_instance

async def clear_redis_cache_data():
    client = await get_redis_client()
    try:
        await client.flushdb()
        print("Redis cache cleared successfully.")
    except Exception as e:
        print(f"Error clearing Redis cache: {e}")