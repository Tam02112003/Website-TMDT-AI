import asyncpg
from typing import List, Optional
from schemas import schemas

REVIEW_SELECT = """
    SELECT r.id, r.product_id, r.user_id, r.username, r.rating, r.content, r.verified_purchase, r.created_at, r.updated_at, u.avatar_url as user_avatar_url
    FROM reviews r
    LEFT JOIN users u ON r.user_id = u.id
"""

def _row_to_review(row) -> schemas.Review:
    return schemas.Review(**dict(row))

async def get_reviews_by_product(db: asyncpg.Connection, product_id: int, skip: int = 0, limit: int = 50) -> List[schemas.Review]:
    rows = await db.fetch(
        REVIEW_SELECT + " WHERE r.product_id = $1 AND r.is_active = TRUE ORDER BY r.created_at DESC OFFSET $2 LIMIT $3",
        product_id, skip, limit
    )
    return [_row_to_review(row) for row in rows]

async def get_review_by_id(db: asyncpg.Connection, review_id: int) -> Optional[schemas.Review]:
    row = await db.fetchrow(REVIEW_SELECT + " WHERE r.id = $1", review_id)
    return _row_to_review(row) if row else None

async def get_review_by_user_and_product(db: asyncpg.Connection, product_id: int, user_id: int) -> Optional[schemas.Review]:
    row = await db.fetchrow(
        REVIEW_SELECT + " WHERE r.product_id = $1 AND r.user_id = $2 AND r.is_active = TRUE",
        product_id, user_id
    )
    return _row_to_review(row) if row else None

async def has_purchased_product(db: asyncpg.Connection, user_id: int, product_id: int) -> bool:
    row = await db.fetchrow(
        """
        SELECT 1 FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        WHERE o.user_id = $1 AND oi.product_id = $2 AND o.status IN ('paid', 'delivered')
        LIMIT 1
        """,
        user_id, product_id
    )
    return row is not None

async def create_review(db: asyncpg.Connection, product_id: int, user_id: int, username: str, review: schemas.ReviewCreate) -> schemas.Review:
    verified_purchase = await has_purchased_product(db, user_id, product_id)
    row = await db.fetchrow(
        """
        INSERT INTO reviews (product_id, user_id, username, rating, content, verified_purchase)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        product_id, user_id, username, review.rating, review.content, verified_purchase
    )
    return await get_review_by_id(db, row["id"])

async def update_review(db: asyncpg.Connection, review_id: int, review: schemas.ReviewUpdate) -> Optional[schemas.Review]:
    row = await db.fetchrow(
        "UPDATE reviews SET rating=$1, content=$2, updated_at=NOW() WHERE id=$3 RETURNING id",
        review.rating, review.content, review_id
    )
    if not row:
        return None
    return await get_review_by_id(db, review_id)

async def delete_review(db: asyncpg.Connection, review_id: int) -> bool:
    row = await db.fetchrow("UPDATE reviews SET is_active=FALSE, updated_at=NOW() WHERE id=$1 AND is_active=TRUE RETURNING id", review_id)
    return row is not None

async def get_rating_summary(db: asyncpg.Connection, product_id: int) -> schemas.ReviewSummary:
    row = await db.fetchrow(
        "SELECT ROUND(AVG(rating)::numeric, 1)::float as avg_rating, COUNT(*) as review_count FROM reviews WHERE product_id = $1 AND is_active = TRUE",
        product_id
    )
    return schemas.ReviewSummary(avg_rating=row["avg_rating"], review_count=row["review_count"])
