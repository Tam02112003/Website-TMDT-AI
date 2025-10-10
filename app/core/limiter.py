from slowapi import Limiter
from slowapi.util import get_remote_address
from core.settings import settings

# Construct Redis URL from settings
redis_password = settings.REDIS.PASSWORD.get_secret_value()
redis_url = f"redis://:{redis_password}@{settings.REDIS.HOST}:{settings.REDIS.PORT}/{settings.REDIS.DB}"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_url,
    strategy="fixed-window",
)
