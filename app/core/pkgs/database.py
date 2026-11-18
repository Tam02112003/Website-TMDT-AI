from core.settings import settings
import asyncpg

DATABASE_URL = settings.DB.DATABASE_URL

class ConnectionPool:
    def __init__(self, dsn):
        self._pool = None
        self._dsn = dsn

    async def get_pool(self):
        if self._pool is None:
            ssl_mode = "require" if settings.DB.HOST not in ("localhost", "127.0.0.1") else None
            # statement_cache_size=0: required for compatibility with PgBouncer's
            # transaction pooling mode (used by Neon's pooler endpoint) - asyncpg's
            # server-side prepared statements don't work reliably through it.
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=settings.DB.MIN_POOL_SIZE,
                max_size=settings.DB.MAX_POOL_SIZE,
                ssl=ssl_mode,
                statement_cache_size=0,
            )
        return self._pool

connection_pool = ConnectionPool(DATABASE_URL)

async def get_db():
    pool = await connection_pool.get_pool()
    async with pool.acquire() as conn:
        yield conn