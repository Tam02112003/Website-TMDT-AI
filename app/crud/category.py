import asyncpg
from typing import Optional, List
from schemas import schemas

async def get_categories(db: asyncpg.Connection) -> List[schemas.Category]:
    rows = await db.fetch("SELECT id, name FROM categories")
    return [schemas.Category(id=row['id'], name=row['name']) for row in rows]

async def get_category_by_id(db: asyncpg.Connection, category_id: int) -> Optional[schemas.Category]:
    row = await db.fetchrow("SELECT id, name FROM categories WHERE id = $1", category_id)
    if row:
        return schemas.Category(id=row['id'], name=row['name'])
    return None

async def create_category(db: asyncpg.Connection, category: schemas.CategoryCreate) -> schemas.Category:
    row = await db.fetchrow("INSERT INTO categories (name) VALUES ($1) RETURNING id, name", category.name)
    return schemas.Category(id=row['id'], name=row['name'])

async def update_category(db: asyncpg.Connection, category_id: int, category: schemas.CategoryCreate) -> Optional[schemas.Category]:
    row = await db.fetchrow("UPDATE categories SET name = $1 WHERE id = $2 RETURNING id, name", category.name, category_id)
    if row:
        return schemas.Category(id=row['id'], name=row['name'])
    return None

async def delete_category(db: asyncpg.Connection, category_id: int) -> Optional[schemas.Category]:
    row = await db.fetchrow("DELETE FROM categories WHERE id = $1 RETURNING id, name", category_id)
    if row:
        return schemas.Category(id=row['id'], name=row['name'])
    return None
