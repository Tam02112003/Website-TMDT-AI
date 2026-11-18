from slowapi import Limiter
from slowapi.util import get_remote_address
from core.settings import settings

# Construct Redis URL from settings
redis_password = settings.REDIS.PASSWORD.get_secret_value()
redis_scheme = "rediss" if settings.REDIS.HOST not in ("localhost", "127.0.0.1") else "redis"
redis_url = f"{redis_scheme}://:{redis_password}@{settings.REDIS.HOST}:{settings.REDIS.PORT}/{settings.REDIS.DB}"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_url,
    strategy="fixed-window",
)
