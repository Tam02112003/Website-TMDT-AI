import asyncpg
from typing import List
from schemas import schemas
from crud.product import get_products_by_ids


async def get_wishlist(db: asyncpg.Connection, user_id: int) -> List[schemas.Product]:
    rows = await db.fetch(
        "SELECT product_id FROM wishlist WHERE user_id = $1 ORDER BY created_at DESC", user_id
    )
    product_ids = [row["product_id"] for row in rows]
    products_by_id = await get_products_by_ids(db, product_ids)
    # Preserve wishlist order (most recently added first); a product removed/
    # deactivated elsewhere just silently drops out of the result.
    return [products_by_id[pid] for pid in product_ids if pid in products_by_id]


async def get_wishlist_product_ids(db: asyncpg.Connection, user_id: int) -> List[int]:
    rows = await db.fetch("SELECT product_id FROM wishlist WHERE user_id = $1", user_id)
    return [row["product_id"] for row in rows]


async def add_to_wishlist(db: asyncpg.Connection, user_id: int, product_id: int):
    await db.execute(
        "INSERT INTO wishlist (user_id, product_id) VALUES ($1, $2) ON CONFLICT (user_id, product_id) DO NOTHING",
        user_id, product_id,
    )


async def remove_from_wishlist(db: asyncpg.Connection, user_id: int, product_id: int):
    await db.execute("DELETE FROM wishlist WHERE user_id = $1 AND product_id = $2", user_id, product_id)
