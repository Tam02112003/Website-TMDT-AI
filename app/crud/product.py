import asyncpg
from typing import Optional, List, Dict
from schemas import schemas
from datetime import datetime
import json
from core.app_config import logger
from crud.discount import to_vietnam_aware
from core.utils.slug import make_product_slug

PRODUCT_DETAIL_SELECT = """
    SELECT p.id, p.name, p.slug, p.description, p.price, p.quantity, p.image_urls, p.is_active, p.is_ai_generated, p.created_at, p.updated_at, p.release_date,
           p.switch_type, p.layout, p.hot_swappable,
           c.id as category_id, c.name as category_name,
           b.id as brand_id, b.name as brand_name,
           d.percent as discount_percent, d.start_date, d.end_date,
           r.avg_rating, COALESCE(r.review_count, 0) as review_count
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    LEFT JOIN brands b ON p.brand_id = b.id
    LEFT JOIN discounts d ON p.id = d.product_id AND d.is_active = TRUE AND d.start_date <= (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::timestamp AND d.end_date >= (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::timestamp
    LEFT JOIN (
        SELECT product_id, ROUND(AVG(rating)::numeric, 1)::float as avg_rating, COUNT(*) as review_count
        FROM reviews WHERE is_active = TRUE GROUP BY product_id
    ) r ON r.product_id = p.id
"""

def _row_to_product(row) -> schemas.Product:
    product_data = dict(row)
    if product_data.get("image_urls"):
        try:
            product_data["image_urls"] = json.loads(product_data["image_urls"])
        except json.JSONDecodeError:
            product_data["image_urls"] = [product_data["image_urls"]]
    else:
        product_data["image_urls"] = []

    discount_percent = product_data.pop("discount_percent", None)
    start_date = to_vietnam_aware(product_data.pop("start_date", None))
    end_date = to_vietnam_aware(product_data.pop("end_date", None))
    final_price = product_data["price"]
    if discount_percent is not None:
        final_price = product_data["price"] * (1 - discount_percent / 100)
    
    category_data = {"id": product_data["category_id"], "name": product_data.pop("category_name")} if product_data.get("category_id") else None
    brand_data = {"id": product_data["brand_id"], "name": product_data.pop("brand_name")} if product_data.get("brand_id") else None
    
    return schemas.Product(**product_data, discount_percent=discount_percent, final_price=final_price, start_date=start_date, end_date=end_date, category=category_data, brand=brand_data)

async def _get_full_product_details_by_id(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    """Internal helper to fetch a product by ID, irrespective of its is_active status."""
    row = await db.fetchrow(PRODUCT_DETAIL_SELECT + " WHERE p.id = $1", product_id)
    if not row:
        return None
    return _row_to_product(row)

async def get_products_by_ids(db: asyncpg.Connection, product_ids: List[int]) -> Dict[int, schemas.Product]:
    """Batch-fetch products by id in a single query. Returns a {id: Product} map."""
    if not product_ids:
        return {}
    rows = await db.fetch(PRODUCT_DETAIL_SELECT + " WHERE p.id = ANY($1::int[])", product_ids)
    return {row["id"]: _row_to_product(row) for row in rows}

async def get_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100, search_query: Optional[str] = None, category_id: Optional[int] = None, brand_id: Optional[int] = None, min_price: Optional[float] = None, max_price: Optional[float] = None, switch_type: Optional[str] = None, layout: Optional[str] = None, hot_swappable: Optional[bool] = None) -> List[schemas.Product]:
    # This function is for public-facing queries, so it correctly filters for is_active = TRUE
    query = PRODUCT_DETAIL_SELECT + " WHERE p.is_active = TRUE"
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
    if switch_type:
        query += f" AND p.switch_type = ${param_idx}"
        params.append(switch_type)
        param_idx += 1
    if layout:
        query += f" AND p.layout = ${param_idx}"
        params.append(layout)
        param_idx += 1
    if hot_swappable is not None:
        query += f" AND p.hot_swappable = ${param_idx}"
        params.append(hot_swappable)
        param_idx += 1

    query += f" ORDER BY p.id OFFSET ${param_idx} LIMIT ${param_idx + 1}"
    params.extend([skip, limit])

    rows = await db.fetch(query, *params)
    return [_row_to_product(row) for row in rows]

async def get_discounted_products(db: asyncpg.Connection, limit: int = 6) -> List[schemas.Product]:
    """Active products with a currently-active discount, highest % first.
    Used to source content for promotional marketing emails."""
    query = PRODUCT_DETAIL_SELECT + """
        WHERE p.is_active = TRUE
          AND d.id IS NOT NULL
        ORDER BY d.percent DESC
        LIMIT $1
    """
    rows = await db.fetch(query, limit)
    return [_row_to_product(row) for row in rows]

async def get_all_product_names(db: asyncpg.Connection) -> List[str]:
    """Lightweight name-only fetch (active + inactive) used for de-duplication,
    e.g. before creating AI-researched product candidates."""
    rows = await db.fetch("SELECT name FROM products")
    return [row["name"] for row in rows]

async def get_products_by_keywords(db: asyncpg.Connection, keywords: List[str], limit: int = 200) -> List[schemas.Product]:
    """Fetches active products whose name or description matches ANY of the given
    keywords (OR'd ILIKE). Used as the candidate set for semantic search, which
    then ranks these client-side by keyword-overlap score."""
    if not keywords:
        return []

    conditions = []
    params: List[str] = []
    for i, kw in enumerate(keywords, start=1):
        conditions.append(f"(p.name ILIKE ${i} OR p.description ILIKE ${i})")
        params.append(f"%{kw}%")

    query = PRODUCT_DETAIL_SELECT + f" WHERE p.is_active = TRUE AND ({' OR '.join(conditions)})"
    query += f" LIMIT ${len(params) + 1}"
    params.append(limit)

    rows = await db.fetch(query, *params)
    return [_row_to_product(row) for row in rows]

async def get_product_by_id(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    product = await _get_full_product_details_by_id(db, product_id)
    if product and product.is_active:
        return product
    return None

async def get_product_by_slug(db: asyncpg.Connection, slug: str) -> Optional[schemas.Product]:
    row = await db.fetchrow(PRODUCT_DETAIL_SELECT + " WHERE p.slug = $1", slug)
    if not row:
        return None
    product = _row_to_product(row)
    return product if product.is_active else None

async def get_product_by_identifier(db: asyncpg.Connection, identifier: str) -> Optional[schemas.Product]:
    """Looks a product up by its slug, falling back to a numeric id for
    backward-compatible/internal links (e.g. old bookmarked /products/{id} URLs)."""
    product = await get_product_by_slug(db, identifier)
    if product:
        return product
    if identifier.isdigit():
        return await get_product_by_id(db, int(identifier))
    return None

async def create_product(db: asyncpg.Connection, product: schemas.ProductCreate) -> schemas.Product:
    image_urls_json = json.dumps(product.image_urls) if product.image_urls else None
    release_date = product.release_date
    if release_date and release_date.tzinfo:
        release_date = release_date.replace(tzinfo=None)
    row = await db.fetchrow("""
        INSERT INTO products (name, description, price, quantity, image_urls, is_active, is_ai_generated, release_date, brand_id, category_id, switch_type, layout, hot_swappable)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING id
    """,
        product.name, product.description, product.price, product.quantity, image_urls_json, product.is_active, bool(product.is_ai_generated), release_date, product.brand_id, product.category_id, product.switch_type, product.layout, bool(product.hot_swappable)
    )
    product_id = row["id"]
    await db.execute("UPDATE products SET slug = $1 WHERE id = $2", make_product_slug(product.name, product_id), product_id)
    return await _get_full_product_details_by_id(db, product_id)

async def update_product(db: asyncpg.Connection, product_id: int, product: schemas.ProductUpdate) -> Optional[schemas.Product]:
    # This function can update an inactive product, so it uses the helper directly.
    # is_ai_generated is intentionally NOT reset here - once an admin edits/approves
    # a candidate it should still be traceable as AI-sourced, just no longer pending.
    image_urls_json = json.dumps(product.image_urls) if product.image_urls else None
    release_date = product.release_date
    if release_date and release_date.tzinfo:
        release_date = release_date.replace(tzinfo=None)
    row = await db.fetchrow("""
        UPDATE products SET name=$1, description=$2, price=$3, quantity=$4, image_urls=$5, is_active=$6, release_date=$7, brand_id=$8, category_id=$9, switch_type=$10, layout=$11, hot_swappable=$12, updated_at=NOW()
        WHERE id = $13
        RETURNING id
    """,
        product.name, product.description, product.price, product.quantity, image_urls_json, product.is_active, release_date, product.brand_id, product.category_id, product.switch_type, product.layout, bool(product.hot_swappable), product_id
    )
    if row:
        return await _get_full_product_details_by_id(db, product_id)
    return None

async def delete_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    # First, check if the product exists and is active
    product = await get_product_by_id(db, product_id)
    if not product:
        return None
    # Then, deactivate it
    await db.execute("UPDATE products SET is_active=FALSE, updated_at=NOW() WHERE id = $1", product_id)
    # Return the full details of the now-inactive product
    return await _get_full_product_details_by_id(db, product_id)

async def get_deleted_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Product]:
    # Excludes pending AI candidates (is_ai_generated) - those were never a real,
    # previously-live product, so they don't belong in the "deleted" trash view;
    # see get_pending_ai_products for those.
    rows = await db.fetch(
        PRODUCT_DETAIL_SELECT + " WHERE p.is_active = FALSE AND p.is_ai_generated = FALSE ORDER BY p.id OFFSET $1 LIMIT $2",
        skip, limit
    )
    return [_row_to_product(row) for row in rows]

async def get_pending_ai_products(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Product]:
    """Products created from AI research, not yet reviewed/activated by an admin."""
    rows = await db.fetch(
        PRODUCT_DETAIL_SELECT + " WHERE p.is_active = FALSE AND p.is_ai_generated = TRUE ORDER BY p.id OFFSET $1 LIMIT $2",
        skip, limit
    )
    return [_row_to_product(row) for row in rows]

async def restore_product(db: asyncpg.Connection, product_id: int) -> Optional[schemas.Product]:
    await db.execute("UPDATE products SET is_active=TRUE, updated_at=NOW() WHERE id = $1", product_id)
    # CORRECTED: Use the internal helper to return the now-active product
    return await _get_full_product_details_by_id(db, product_id)

# ... (rest of the comment functions remain the same)

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