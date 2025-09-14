import asyncpg
from typing import List, Optional
from schemas import schemas

async def get_news(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.News]:
    rows = await db.fetch("SELECT id, title, content, is_active, created_at, updated_at FROM news WHERE is_active=TRUE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    return [schemas.News(
        id=row["id"], title=row["title"], content=row["content"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
    ) for row in rows]

async def get_news_item(db: asyncpg.Connection, news_id: int) -> Optional[schemas.News]:
    row = await db.fetchrow("SELECT id, title, content, is_active, created_at, updated_at FROM news WHERE id = $1 AND is_active=TRUE", news_id)
    if row:
        return schemas.News(
            id=row["id"], title=row["title"], content=row["content"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
    return None

async def create_news(db: asyncpg.Connection, news: schemas.NewsCreate) -> schemas.News:
    row = await db.fetchrow("""
        INSERT INTO news (title, content)
        VALUES ($1, $2) RETURNING id, created_at, updated_at
    """, news.title, news.content)
    return schemas.News(
        id=row["id"], title=news.title, content=news.content, created_at=row["created_at"], updated_at=row["updated_at"]
    )

async def update_news(db: asyncpg.Connection, news_id: int, news: schemas.NewsUpdate) -> Optional[schemas.News]:
    row = await db.fetchrow("""
        UPDATE news SET title=$1, content=$2, updated_at=NOW()
        WHERE id=$3 RETURNING id, title, content, created_at, updated_at
    """, news.title, news.content, news_id)
    if row:
        return schemas.News(
            id=row["id"], title=row["title"], content=row["content"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
    return None

async def delete_news(db: asyncpg.Connection, news_id: int) -> Optional[schemas.News]:
    news_item = await get_news_item(db, news_id)
    if not news_item:
        return None
    row = await db.fetchrow("UPDATE news SET is_active=FALSE, updated_at=NOW() WHERE id = $1 RETURNING id, title, content, is_active, created_at, updated_at", news_id)
    if row:
        return schemas.News(
            id=row["id"], title=row["title"], content=row["content"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
    return None

async def get_deleted_news(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.News]:
    rows = await db.fetch("SELECT id, title, content, is_active, created_at, updated_at FROM news WHERE is_active=FALSE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    return [schemas.News(
        id=row["id"], title=row["title"], content=row["content"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
    ) for row in rows]

async def restore_news(db: asyncpg.Connection, news_id: int) -> Optional[schemas.News]:
    row = await db.fetchrow("""
        UPDATE news SET is_active=TRUE, updated_at=NOW()
        WHERE id=$1 RETURNING id, title, content, is_active, created_at, updated_at
    """, news_id)
    if row:
        return schemas.News(
            id=row["id"], title=row["title"], content=row["content"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
    return None
