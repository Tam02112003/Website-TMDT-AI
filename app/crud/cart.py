import asyncpg
from typing import List
import json
from datetime import datetime
import pytz
from fastapi import HTTPException
from redis.asyncio import Redis
from crud.product import get_product_by_id
from crud.discount import to_vietnam_aware

VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

async def get_cart(db: asyncpg.Connection, user_id: int, redis_client: Redis) -> List[dict]:
    cart_key = f"cart:{user_id}"
    cart_data = await redis_client.get(cart_key)
    if cart_data:
        return json.loads(cart_data)
    
    items = await db.fetch("SELECT * FROM cart WHERE user_id = $1", user_id)

    processed_items = []
    for item in items:
        processed_item = dict(item)
        for key, value in processed_item.items():
            if isinstance(value, datetime):
                processed_item[key] = value.isoformat()
        processed_items.append(processed_item)

    await redis_client.set(cart_key, json.dumps(processed_items), ex=3600)
    return processed_items

async def _assert_product_purchasable(db: asyncpg.Connection, product_id: int, total_quantity_wanted: int):
    """Shared guard so adding to cart can't be used to bypass what the storefront
    UI merely disables the button for: an inactive product, a product not yet
    released, or a quantity beyond what's in stock. `total_quantity_wanted` is
    the cart quantity AFTER this change, not just the delta being added."""
    product = await get_product_by_id(db, product_id)  # already filters is_active=True
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại hoặc đã ngừng kinh doanh.")

    if product.release_date:
        release_date_aware = to_vietnam_aware(product.release_date)
        if release_date_aware and release_date_aware > datetime.now(VIETNAM_TZ):
            raise HTTPException(status_code=400, detail="Sản phẩm chưa đến ngày mở bán.")

    if total_quantity_wanted > (product.quantity or 0):
        raise HTTPException(status_code=400, detail=f"Chỉ còn {product.quantity or 0} sản phẩm trong kho.")

async def add_to_cart(db: asyncpg.Connection, user_id: int, product_id: int, quantity: int, redis_client: Redis):
    # Check if product already exists in cart
    existing_item = await db.fetchrow("SELECT quantity FROM cart WHERE user_id = $1 AND product_id = $2", user_id, product_id)
    new_quantity = (existing_item['quantity'] if existing_item else 0) + quantity

    await _assert_product_purchasable(db, product_id, new_quantity)

    if existing_item:
        await db.execute("UPDATE cart SET quantity = $1 WHERE user_id = $2 AND product_id = $3", new_quantity, user_id, product_id)
    else:
        await db.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES ($1, $2, $3)", user_id, product_id, quantity)

    await redis_client.delete(f"cart:{user_id}")

async def update_cart(db: asyncpg.Connection, user_id: int, product_id: int, quantity: int, redis_client: Redis):
    await _assert_product_purchasable(db, product_id, quantity)
    await db.execute("UPDATE cart SET quantity = $1 WHERE user_id = $2 AND product_id = $3", quantity, user_id, product_id)
    await redis_client.delete(f"cart:{user_id}")

async def remove_from_cart(db: asyncpg.Connection, user_id: int, product_id: int, redis_client: Redis):
    await db.execute("DELETE FROM cart WHERE user_id = $1 AND product_id = $2", user_id, product_id)
    await redis_client.delete(f"cart:{user_id}")

async def clear_cart(db: asyncpg.Connection, user_id: int, redis_client: Redis):
    await db.execute("DELETE FROM cart WHERE user_id = $1", user_id)
    await redis_client.delete(f"cart:{user_id}")
