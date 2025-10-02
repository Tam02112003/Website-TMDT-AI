import asyncpg
from typing import Optional, List
from schemas import schemas
from datetime import datetime
import json
from core.app_config import logger # Import logger
from crud.discount import to_vietnam_aware # Import to_vietnam_aware

async def get_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100, search_query: Optional[str] = None, category_id: Optional[int] = None, brand_id: Optional[int] = None, min_price: Optional[float] = None, max_price: Optional[float] = None) -> List[schemas.Product]:
    query = """
        SELECT p.id, p.name, p.description, p.price, p.quantity, p.image_urls, p.is_active, p.created_at, p.updated_at, p.release_date,
               c.id as category_id, c.name as category_name,
               b.id as brand_id, b.name as brand_name,
               d.percent as discount_percent, d.start_date, d.end_date
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
        LEFT JOIN discounts d ON p.id = d.product_id AND d.is_active = TRUE AND d.start_date <= (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::timestamp AND d.end_date >= (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::timestamp
        WHERE p.is_active = TRUE
    """
    params = []
    param_idx = 1
    if search_query:
        query += f" AND p.name ILIKE ${param_idx}"
        params.append(f'%{search_query}%')
        param_idx += 1
    if category_id:
        query += f" AND p.category_id = ${param_idx}"
        params.append(category_id)
        param_idx += 1
    if brand_id:
        query += f" AND p.brand_id = ${param_idx}"
        params.append(brand_id)
        param_idx += 1
    if min_price is not None:
        query += f" AND p.price >= ${param_idx}"
        params.append(min_price)
        param_idx += 1
    if max_price is not None:
        query += f" AND p.price <= ${param_idx}"
        params.append(max_price)
        param_idx += 1

    query += f" ORDER BY p.id OFFSET ${param_idx} LIMIT ${param_idx + 1}"
    params.extend([skip, limit])

    rows = await db.fetch(query, *params)
    products = []
    for row in rows:
        product_data = dict(row)
        if product_data["image_urls"]:
            try:
                product_data["image_urls"] = json.loads(product_data["image_urls"])
            except json.JSONDecodeError:
                product_data["image_urls"] = [product_data["image_urls"]]
        else:
            product_data["image_urls"] = []

        discount_percent = product_data.pop("discount_percent")
        start_date = to_vietnam_aware(product_data.pop("start_date"))
        end_date = to_vietnam_aware(product_data.pop("end_date"))
        final_price = product_data["price"]
        if discount_percent is not None:
            final_price = product_data["price"] * (1 - discount_percent / 100)

        category_data = {"id": product_data["category_id"], "name": product_data.pop("category_name")} if product_data.get("category_id") else None
        brand_data = {"id": product_data["brand_id"], "name": product_data.pop("brand_name")} if product_data.get("brand_id") else None

        products.append(schemas.Product(**product_data, discount_percent=discount_percent, final_price=final_price, start_date=start_date, end_date=end_date, category=category_data, brand=brand_data))
    return products

async def get_product_by_id(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    row = await db.fetchrow("""
        SELECT p.id, p.name, p.description, p.price, p.quantity, p.image_urls, p.is_active, p.created_at, p.updated_at, p.release_date,
               c.id as category_id, c.name as category_name,
               b.id as brand_id, b.name as brand_name,
               d.percent as discount_percent, d.start_date, d.end_date
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
        LEFT JOIN discounts d ON p.id = d.product_id AND d.is_active = TRUE AND d.start_date <= (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::timestamp AND d.end_date >= (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::timestamp
        WHERE p.id = $1 AND p.is_active = TRUE
    """, product_id)
    if row:
        product_data = dict(row)
        if product_data["image_urls"]:
            try:
                product_data["image_urls"] = json.loads(product_data["image_urls"])
            except json.JSONDecodeError:
                product_data["image_urls"] = [product_data["image_urls"]]
        else:
            product_data["image_urls"] = []

        discount_percent = product_data.pop("discount_percent")
        start_date = to_vietnam_aware(product_data.pop("start_date"))
        end_date = to_vietnam_aware(product_data.pop("end_date"))
        final_price = product_data["price"]
        if discount_percent is not None:
            final_price = product_data["price"] * (1 - discount_percent / 100)
        
        category_data = {"id": product_data["category_id"], "name": product_data.pop("category_name")} if product_data.get("category_id") else None
        brand_data = {"id": product_data["brand_id"], "name": product_data.pop("brand_name")} if product_data.get("brand_id") else None
        return schemas.Product(**product_data, discount_percent=discount_percent, final_price=final_price, start_date=start_date, end_date=end_date, category=category_data, brand=brand_data)
    return None

async def create_product(db: asyncpg.Connection, product: schemas.ProductCreate) -> schemas.Product:
    image_urls_json = json.dumps(product.image_urls) if product.image_urls else None
    release_date = product.release_date
    if release_date and release_date.tzinfo:
        release_date = release_date.replace(tzinfo=None)
    row = await db.fetchrow("""
        INSERT INTO products (name, description, price, quantity, image_urls, is_active, release_date, brand_id, category_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id, name, description, price, quantity, image_urls, is_active, created_at, updated_at, release_date, brand_id, category_id
    """,
        product.name, product.description, product.price, product.quantity, image_urls_json, product.is_active, release_date, product.brand_id, product.category_id
    )
    product_data = dict(row)
    if product_data["image_urls"]:
        try:
            product_data["image_urls"] = json.loads(product_data["image_urls"])
        except json.JSONDecodeError:
            product_data["image_urls"] = [product_data["image_urls"]]
    else:
        product_data["image_urls"] = []
    return await get_product_by_id(db, product_data["id"])

async def update_product(db: asyncpg.Connection, product_id: int, product: schemas.ProductUpdate) -> Optional[schemas.Product]:
    logger.info(f"Attempting to update product_id: {product_id} with data: {product.model_dump_json()}")
    image_urls_json = json.dumps(product.image_urls) if product.image_urls else None
    release_date = product.release_date
    if release_date and release_date.tzinfo:
        release_date = release_date.replace(tzinfo=None)
    row = await db.fetchrow("""
        UPDATE products SET name=$1, description=$2, price=$3, quantity=$4, image_urls=$5, is_active=$6, release_date=$7, brand_id=$8, category_id=$9, updated_at=NOW()
        WHERE id = $10
        RETURNING id, name, description, price, quantity, image_urls, is_active, created_at, updated_at, release_date, brand_id, category_id
    """,
        product.name, product.description, product.price, product.quantity, image_urls_json, product.is_active, release_date, product.brand_id, product.category_id, product_id
    )
    if row:
        logger.info(f"Successfully updated product_id: {product_id}")
        return await get_product_by_id(db, product_id)
    logger.warning(f"Failed to update product_id: {product_id}. Product not found or update failed.")
    return None

async def delete_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    product = await get_product_by_id(db, product_id)
    if not product:
        return None
    row = await db.fetchrow("UPDATE products SET is_active=FALSE, updated_at=NOW() WHERE id = $1 RETURNING id", product_id)
    if row:
        return await get_product_by_id(db, row['id'])
    return None

async def get_deleted_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Product]:
    rows = await db.fetch("SELECT id FROM products WHERE is_active=FALSE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    products = []
    for row in rows:
        product = await get_product_by_id(db, row['id'])
        if product:
            products.append(product)
    return products

async def restore_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    row = await db.fetchrow("UPDATE products SET is_active=TRUE, updated_at=NOW() WHERE id = $1 RETURNING id", product_id)
    if row:
        return await get_product_by_id(db, row['id'])
    return None

async def create_comment(db: asyncpg.Connection, comment: schemas.CommentCreate) -> schemas.Comment:
    row = await db.fetchrow("""
        INSERT INTO comments (product_id, content, user_name, parent_comment_id, created_at)
        VALUES ($1, $2, $3, $4, NOW()) RETURNING id, product_id, content, user_name, parent_comment_id, created_at
    """, comment.product_id, comment.content, comment.user_name, comment.parent_comment_id)
    return schemas.Comment(
        id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], parent_comment_id=row["parent_comment_id"], created_at=row["created_at"]
    )

async def get_comments(db: asyncpg.Connection, product_id: int) -> list[schemas.Comment]:
    rows = await db.fetch("""
        SELECT c.id, c.product_id, c.content, c.user_name, c.parent_comment_id, c.created_at, u.avatar_url as user_avatar_url
        FROM comments c
        LEFT JOIN users u ON c.user_name = u.username
        WHERE c.product_id=$1 ORDER BY c.created_at DESC
    """, product_id)
    return [schemas.Comment(id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], parent_comment_id=row["parent_comment_id"], created_at=row["created_at"], user_avatar_url=row["user_avatar_url"]) for row in rows]

async def delete_comment(db: asyncpg.Connection, comment_id: int) -> bool:
    row = await db.fetchrow("DELETE FROM comments WHERE id=$1 RETURNING id", comment_id)
    return bool(row)

async def get_comment_by_id(db: asyncpg.Connection, comment_id: int) -> schemas.Comment | None:
    row = await db.fetchrow("SELECT id, product_id, content, user_name, parent_comment_id, created_at FROM comments WHERE id=$1", comment_id)
    if row:
        return schemas.Comment(id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], parent_comment_id=row["parent_comment_id"], created_at=row["created_at"])
    return None

async def update_comment(db: asyncpg.Connection, comment_id: int, new_content: str) -> Optional[schemas.Comment]:
    row = await db.fetchrow("UPDATE comments SET content=$1, created_at=NOW() WHERE id=$2 RETURNING id, product_id, content, user_name, created_at", new_content, comment_id)
    if row:
        return schemas.Comment(id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], created_at=row["created_at"])
    return None

async def restore_comment(db: asyncpg.Connection, comment_id: int) -> Optional[schemas.Comment]:
    row = await db.fetchrow("""
        UPDATE comments SET is_active=TRUE
        WHERE id=$1 RETURNING id, product_id, content, user_name, created_at
    """, comment_id)
    if row:
        return schemas.Comment(
            id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], created_at=row["created_at"]
        )
    return None

async def get_deleted_comments(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Comment]:
    rows = await db.fetch("SELECT id, product_id, content, user_name, created_at FROM comments WHERE is_active=FALSE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    return [schemas.Comment(
        id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], created_at=row["created_at"]
    ) for row in rows]
