import asyncpg
from typing import List
import json
from datetime import datetime
from redis.asyncio import Redis

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

async def add_to_cart(db: asyncpg.Connection, user_id: int, product_id: int, quantity: int, redis_client: Redis):
    # Check if product already exists in cart
    existing_item = await db.fetchrow("SELECT quantity FROM cart WHERE user_id = $1 AND product_id = $2", user_id, product_id)

    if existing_item:
        new_quantity = existing_item['quantity'] + quantity
        await db.execute("UPDATE cart SET quantity = $1 WHERE user_id = $2 AND product_id = $3", new_quantity, user_id, product_id)
    else:
        await db.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES ($1, $2, $3)", user_id, product_id, quantity)
    
    await redis_client.delete(f"cart:{user_id}")

async def update_cart(db: asyncpg.Connection, user_id: int, product_id: int, quantity: int, redis_client: Redis):
    await db.execute("UPDATE cart SET quantity = $1 WHERE user_id = $2 AND product_id = $3", quantity, user_id, product_id)
    await redis_client.delete(f"cart:{user_id}")

async def remove_from_cart(db: asyncpg.Connection, user_id: int, product_id: int, redis_client: Redis):
    await db.execute("DELETE FROM cart WHERE user_id = $1 AND product_id = $2", user_id, product_id)
    await redis_client.delete(f"cart:{user_id}")

async def clear_cart(db: asyncpg.Connection, user_id: int, redis_client: Redis):
    await db.execute("DELETE FROM cart WHERE user_id = $1", user_id)
    await redis_client.delete(f"cart:{user_id}")
