import asyncpg
from typing import Optional, List
from schemas import schemas
from datetime import datetime

async def get_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100, search_query: Optional[str] = None) -> List[schemas.Product]:
    query = """
        SELECT
            p.id, p.name, p.description, p.price, p.quantity, p.image_url, p.is_active, p.created_at, p.updated_at,
            d.percent AS discount_percent
        FROM products p
        LEFT JOIN discounts d ON p.id = d.product_id
        AND d.is_active = TRUE
        AND d.start_date <= NOW()
        AND (d.end_date IS NULL OR d.end_date >= NOW())
        WHERE p.is_active=TRUE
    """
    params = []
    
    if search_query:
        query += " AND (p.name ILIKE $1 OR p.description ILIKE $1)"
        params.append(f"%{search_query}%")

    query += f" ORDER BY p.id OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}"
    params.extend([skip, limit])

    rows = await db.fetch(query, *params)
    products = []
    for row in rows:
        product_data = dict(row)
        discount_percent = product_data.pop('discount_percent')
        final_price = product_data['price']
        if discount_percent is not None:
            final_price = product_data['price'] * (1 - discount_percent / 100)
        products.append(schemas.Product(**product_data, discount_percent=discount_percent, final_price=final_price))
    return products

async def get_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    query = """
        SELECT
            p.id, p.name, p.description, p.price, p.quantity, p.image_url, p.is_active, p.created_at, p.updated_at,
            d.percent AS discount_percent
        FROM products p
        LEFT JOIN discounts d ON p.id = d.product_id
        AND d.is_active = TRUE
        AND d.start_date <= NOW()
        AND (d.end_date IS NULL OR d.end_date >= NOW())
        WHERE p.id = $1 AND p.is_active=TRUE
    """
    row = await db.fetchrow(query, product_id)
    if row:
        product_data = dict(row)
        discount_percent = product_data.pop('discount_percent')
        final_price = product_data['price']
        if discount_percent is not None:
            final_price = product_data['price'] * (1 - discount_percent / 100)
        return schemas.Product(**product_data, discount_percent=discount_percent, final_price=final_price)
    return None

async def create_product(db: asyncpg.Connection, product: schemas.ProductCreate) -> schemas.Product:
    row = await db.fetchrow("""
        INSERT INTO products (name, description, price, quantity, image_url, is_active)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id, created_at, updated_at
    """, product.name, product.description, product.price, product.quantity, product.image_url, product.is_active)
    return schemas.Product(
        id=row["id"], name=product.name, description=product.description, price=product.price, quantity=product.quantity, image_url=product.image_url, is_active=product.is_active, created_at=row["created_at"], updated_at=row["updated_at"]
    )

async def update_product(db: asyncpg.Connection, product_id: int, product: schemas.ProductUpdate) -> Optional[schemas.Product]:
    row = await db.fetchrow("""
        UPDATE products SET name=$1, description=$2, price=$3, quantity=$4, image_url=$5, is_active=$6, updated_at=NOW()
        WHERE id=$7 RETURNING id, name, description, price, quantity, image_url, is_active, created_at, updated_at
    """, product.name, product.description, product.price, product.quantity, product.image_url, product.is_active, product_id)
    if row:
        return schemas.Product(
            id=row["id"], name=row["name"], description=row["description"], price=row["price"], quantity=row["quantity"], image_url=row["image_url"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
    return None

async def delete_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    product = await get_product(db, product_id)
    if not product:
        return None
    row = await db.fetchrow("UPDATE products SET is_active=FALSE, updated_at=NOW() WHERE id = $1 RETURNING id, name, description, price, quantity, image_url, is_active, created_at, updated_at", product_id)
    if row:
        return schemas.Product(
            id=row["id"], name=row["name"], description=row["description"], price=row["price"], quantity=row["quantity"], image_url=row["image_url"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
    return None

async def get_deleted_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Product]:
    rows = await db.fetch("SELECT id, name, description, price, quantity, image_url, is_active, created_at, updated_at FROM products WHERE is_active=FALSE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    return [schemas.Product(
        id=row["id"], name=row["name"], description=row["description"], price=row["price"], quantity=row["quantity"], image_url=row["image_url"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
    ) for row in rows]

async def restore_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    row = await db.fetchrow("""
        UPDATE products SET is_active=TRUE, updated_at=NOW()
        WHERE id=$1 RETURNING id, name, description, price, quantity, image_url, is_active, created_at, updated_at
    """, product_id)
    if row:
        return schemas.Product(
            id=row["id"], name=row["name"], description=row["description"], price=row["price"], quantity=row["quantity"], image_url=row["image_url"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
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
