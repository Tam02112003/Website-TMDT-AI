import asyncpg
from typing import List, Optional
from schemas import schemas

async def get_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Product]:
    rows = await db.fetch("SELECT id, name, description, price, quantity, image_url, is_active, created_at, updated_at FROM products WHERE is_active=TRUE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    return [schemas.Product(
        id=row["id"], name=row["name"], description=row["description"], price=row["price"], quantity=row["quantity"], image_url=row["image_url"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
    ) for row in rows]

async def get_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    row = await db.fetchrow("SELECT id, name, description, price, quantity, image_url, is_active, created_at, updated_at FROM products WHERE id = $1 AND is_active=TRUE", product_id)
    if row:
        return schemas.Product(
            id=row["id"], name=row["name"], description=row["description"], price=row["price"], quantity=row["quantity"], image_url=row["image_url"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
        )
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
        INSERT INTO comments (product_id, content, user_name, created_at)
        VALUES ($1, $2, $3, NOW()) RETURNING id, product_id, content, user_name, created_at
    """, comment.product_id, comment.content, comment.user_name)
    return schemas.Comment(
        id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], created_at=row["created_at"]
    )

async def get_comments(db: asyncpg.Connection, product_id: int) -> list[schemas.Comment]:
    rows = await db.fetch("SELECT id, product_id, content, user_name, created_at FROM comments WHERE product_id=$1 AND is_active=TRUE ORDER BY created_at DESC", product_id)
    return [schemas.Comment(id=row["id"], product_id=row["product_id"], content=row["content"], user_name=row["user_name"], created_at=row["created_at"]) for row in rows]

async def delete_comment(db: asyncpg.Connection, comment_id: int) -> bool:
    row = await db.fetchrow("UPDATE comments SET is_active=FALSE WHERE id=$1 AND is_active=TRUE RETURNING id", comment_id)
    return bool(row)

async def get_comment_by_id(db: asyncpg.Connection, comment_id: int) -> schemas.Comment | None:
    row = await db.fetchrow("SELECT id, product_id, content, user_name, created_at FROM comments WHERE id=$1 AND is_active=TRUE", comment_id)
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

async def get_all_products(db: asyncpg.Connection) -> List[schemas.Product]:
    rows = await db.fetch("SELECT id, name, description, price, quantity, image_url, is_active, created_at, updated_at FROM products WHERE is_active=TRUE ORDER BY id")
    return [schemas.Product(
        id=row["id"], name=row["name"], description=row["description"], price=row["price"], quantity=row["quantity"], image_url=row["image_url"], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"]
    ) for row in rows]


