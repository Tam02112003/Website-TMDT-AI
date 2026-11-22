from typing import Optional
import json
import redis.asyncio as aioredis
from core.settings import settings

_redis_client_instance: Optional[aioredis.Redis] = None

async def get_redis_client() -> aioredis.Redis:
    global _redis_client_instance
    if _redis_client_instance is None:
        use_tls = settings.REDIS.HOST not in ("localhost", "127.0.0.1")
        _redis_client_instance = aioredis.Redis(
            host=settings.REDIS.HOST,
            port=settings.REDIS.PORT,
            db=settings.REDIS.DB,
            password=settings.REDIS.PASSWORD.get_secret_value(),
            decode_responses=True,
            ssl=use_tls
        )
    return _redis_client_instance

async def invalidate_cache_pattern(client: aioredis.Redis, pattern: str):
    """Deletes every key matching `pattern` (e.g. 'products:list:*')."""
    keys = [key async for key in client.scan_iter(match=pattern)]
    if keys:
        await client.delete(*keys)

JOB_KEY_PREFIX = "job:"
JOB_TTL_SECONDS = 3600

async def set_job_status(client: aioredis.Redis, job_id: str, status: str, result: Optional[dict] = None):
    """Stores a background job's current status/result, used to let a client poll
    for completion of work kicked off via FastAPI BackgroundTasks."""
    payload = {"status": status, "result": result}
    await client.setex(f"{JOB_KEY_PREFIX}{job_id}", JOB_TTL_SECONDS, json.dumps(payload))

async def get_job_status(client: aioredis.Redis, job_id: str) -> Optional[dict]:
    raw = await client.get(f"{JOB_KEY_PREFIX}{job_id}")
    return json.loads(raw) if raw else None

async def clear_redis_cache_data():
    client = await get_redis_client()
    try:
        await client.flushdb()
        print("Redis cache cleared successfully.")
    except Exception as e:
        print(f"Error clearing Redis cache: {e}")