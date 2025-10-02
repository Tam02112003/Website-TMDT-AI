import asyncpg
from typing import Optional, List
from schemas import schemas

async def get_brands(db: asyncpg.Connection) -> List[schemas.Brand]:
    rows = await db.fetch("SELECT id, name FROM brands")
    return [schemas.Brand(id=row['id'], name=row['name']) for row in rows]

async def get_brand_by_id(db: asyncpg.Connection, brand_id: int) -> Optional[schemas.Brand]:
    row = await db.fetchrow("SELECT id, name FROM brands WHERE id = $1", brand_id)
    if row:
        return schemas.Brand(id=row['id'], name=row['name'])
    return None

async def create_brand(db: asyncpg.Connection, brand: schemas.BrandCreate) -> schemas.Brand:
    row = await db.fetchrow("INSERT INTO brands (name) VALUES ($1) RETURNING id, name", brand.name)
    return schemas.Brand(id=row['id'], name=row['name'])

async def update_brand(db: asyncpg.Connection, brand_id: int, brand: schemas.BrandCreate) -> Optional[schemas.Brand]:
    row = await db.fetchrow("UPDATE brands SET name = $1 WHERE id = $2 RETURNING id, name", brand.name, brand_id)
    if row:
        return schemas.Brand(id=row['id'], name=row['name'])
    return None

async def delete_brand(db: asyncpg.Connection, brand_id: int) -> Optional[schemas.Brand]:
    row = await db.fetchrow("DELETE FROM brands WHERE id = $1 RETURNING id, name", brand_id)
    if row:
        return schemas.Brand(id=row['id'], name=row['name'])
    return None
