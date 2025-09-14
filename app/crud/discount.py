from fastapi import HTTPException
from asyncpg.exceptions import ForeignKeyViolationError
import asyncpg
from typing import List, Optional
from schemas import schemas

async def get_discounts(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Discount]:
    rows = await db.fetch("SELECT id, name, percent, start_date, end_date, product_id, is_active FROM discounts WHERE is_active=TRUE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    return [schemas.Discount(
        id=row["id"], name=row["name"], percent=row["percent"], start_date=row["start_date"], end_date=row["end_date"], product_id=row["product_id"], is_active=row["is_active"]
    ) for row in rows]

async def get_discount(db: asyncpg.Connection, discount_id: int) -> Optional[schemas.Discount]:
    row = await db.fetchrow("SELECT id, name, percent, start_date, end_date, product_id, is_active FROM discounts WHERE id = $1 AND is_active=TRUE", discount_id)
    if row:
        return schemas.Discount(
            id=row["id"], name=row["name"], percent=row["percent"], start_date=row["start_date"], end_date=row["end_date"], product_id=row["product_id"], is_active=row["is_active"]
        )
    return None

async def create_discount(db: asyncpg.Connection, discount: schemas.DiscountCreate) -> schemas.Discount:
    try:
        row = await db.fetchrow("""
            INSERT INTO discounts (name, percent, start_date, end_date, product_id)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, discount.name, discount.percent, discount.start_date, discount.end_date, discount.product_id)
    except ForeignKeyViolationError:
        raise HTTPException(status_code=404, detail=f"Product with id {discount.product_id} not found.")
    return schemas.Discount(
        id=row["id"], name=discount.name, percent=discount.percent, start_date=discount.start_date, end_date=discount.end_date, product_id=discount.product_id
    )

async def update_discount(db: asyncpg.Connection, discount_id: int, discount: schemas.DiscountUpdate) -> Optional[schemas.Discount]:
    try:
        row = await db.fetchrow("""
            UPDATE discounts SET name=$1, percent=$2, start_date=$3, end_date=$4, product_id=$5
            WHERE id=$6 RETURNING id, name, percent, start_date, end_date, product_id
        """, discount.name, discount.percent, discount.start_date, discount.end_date, discount.product_id, discount_id)
    except ForeignKeyViolationError:
        raise HTTPException(status_code=404, detail=f"Product with id {discount.product_id} not found.")
    if row:
        return schemas.Discount(
            id=row["id"], name=row["name"], percent=row["percent"], start_date=row["start_date"], end_date=row["end_date"], product_id=row["product_id"]
        )
    return None

async def delete_discount(db: asyncpg.Connection, discount_id: int) -> Optional[schemas.Discount]:
    discount_item = await get_discount(db, discount_id)
    if not discount_item:
        return None
    row = await db.fetchrow("UPDATE discounts SET is_active=FALSE WHERE id = $1 RETURNING id, name, percent, start_date, end_date, product_id, is_active", discount_id)
    if row:
        return schemas.Discount(
            id=row["id"], name=row["name"], percent=row["percent"], start_date=row["start_date"], end_date=row["end_date"], product_id=row["product_id"], is_active=row["is_active"]
        )
    return None

async def get_deleted_discounts(db: asyncpg.Connection, skip: int = 0, limit: int = 100) -> List[schemas.Discount]:
    rows = await db.fetch("SELECT id, name, percent, start_date, end_date, product_id, is_active FROM discounts WHERE is_active=FALSE ORDER BY id OFFSET $1 LIMIT $2", skip, limit)
    return [schemas.Discount(
        id=row["id"], name=row["name"], percent=row["percent"], start_date=row["start_date"], end_date=row["end_date"], product_id=row["product_id"], is_active=row["is_active"]
    ) for row in rows]

async def restore_discount(db: asyncpg.Connection, discount_id: int) -> Optional[schemas.Discount]:
    row = await db.fetchrow("""
        UPDATE discounts SET is_active=TRUE
        WHERE id=$1 RETURNING id, name, percent, start_date, end_date, product_id, is_active
    """, discount_id)
    if row:
        return schemas.Discount(
            id=row["id"], name=row["name"], percent=row["percent"], start_date=row["start_date"], end_date=row["end_date"], product_id=row["product_id"], is_active=row["is_active"]
        )
    return None