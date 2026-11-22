from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncpg
from redis.asyncio import Redis
from schemas import schemas
from crud import review as review_crud
from crud import product as product_crud
from core.pkgs.database import get_db
from core.dependencies import log_activity
from core.redis.redis_client import get_redis_client, invalidate_cache_pattern
from router.product import PRODUCTS_LIST_CACHE_PATTERN

router = APIRouter(prefix="/products/{product_id}/reviews", tags=["Reviews"])

@router.get("/", response_model=List[schemas.Review])
async def read_product_reviews(product_id: int, skip: int = 0, limit: int = 50, db: asyncpg.Connection = Depends(get_db)):
    return await review_crud.get_reviews_by_product(db, product_id, skip, limit)

@router.get("/summary", response_model=schemas.ReviewSummary)
async def read_product_review_summary(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    return await review_crud.get_rating_summary(db, product_id)

@router.post("/", response_model=schemas.Review, status_code=status.HTTP_201_CREATED)
async def create_product_review(
    product_id: int,
    review: schemas.ReviewCreate,
    db: asyncpg.Connection = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    current_user: dict = Depends(log_activity),
):
    product = await product_crud.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = await review_crud.get_review_by_user_and_product(db, product_id, current_user["id"])
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this product")

    created = await review_crud.create_review(db, product_id, current_user["id"], current_user["username"], review)
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return created

@router.put("/{review_id}", response_model=schemas.Review)
async def update_product_review(
    product_id: int,
    review_id: int,
    review: schemas.ReviewUpdate,
    db: asyncpg.Connection = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    current_user: dict = Depends(log_activity),
):
    existing = await review_crud.get_review_by_id(db, review_id)
    if not existing or existing.product_id != product_id:
        raise HTTPException(status_code=404, detail="Review not found")
    if existing.user_id != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized to update this review")

    updated = await review_crud.update_review(db, review_id, review)
    if not updated:
        raise HTTPException(status_code=404, detail="Review not found")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return updated

@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_review(
    product_id: int,
    review_id: int,
    db: asyncpg.Connection = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    current_user: dict = Depends(log_activity),
):
    existing = await review_crud.get_review_by_id(db, review_id)
    if not existing or existing.product_id != product_id:
        raise HTTPException(status_code=404, detail="Review not found")
    if existing.user_id != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized to delete this review")

    deleted = await review_crud.delete_review(db, review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Review not found")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
