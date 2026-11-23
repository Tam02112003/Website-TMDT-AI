from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Request
from redis.asyncio import Redis
import json
import uuid
from schemas import schemas
from crud import product as product_crud
from core.pkgs.database import get_db, connection_pool
import asyncpg
from typing import List
from services.CsvProcessingService import process_csv_and_save
from services.RecommendationService import get_recommendations
from services.SemanticSearchService import semantic_search_products
from core.app_config import logger
from typing import Optional
from core.dependencies import log_activity
from crud.user import require_admin
from core.limiter import limiter
from core.redis.redis_client import get_redis_client, invalidate_cache_pattern, set_job_status, get_job_status

router = APIRouter(prefix="/products", tags=["Products"])

PRODUCTS_LIST_CACHE_PATTERN = "products:list:*"
PRODUCTS_LIST_CACHE_TTL_SECONDS = 60


@router.get("/", response_model=List[schemas.Product])
async def read_products(skip: int = 0, limit: int = 100, search: Optional[str] = None, category_id: Optional[int] = None, brand_id: Optional[int] = None, min_price: Optional[float] = None, max_price: Optional[float] = None, switch_type: Optional[str] = None, layout: Optional[str] = None, hot_swappable: Optional[bool] = None, db: asyncpg.Connection = Depends(get_db), redis_client: Redis = Depends(get_redis_client)):
    cache_key = f"products:list:{skip}:{limit}:{search}:{category_id}:{brand_id}:{min_price}:{max_price}:{switch_type}:{layout}:{hot_swappable}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return [schemas.Product(**p) for p in json.loads(cached)]
    except Exception as e:
        logger.warning(f"Redis cache read failed for products list, falling back to DB: {e}")

    products = await product_crud.get_products(db, skip=skip, limit=limit, search_query=search, category_id=category_id, brand_id=brand_id, min_price=min_price, max_price=max_price, switch_type=switch_type, layout=layout, hot_swappable=hot_swappable)

    try:
        await redis_client.setex(cache_key, PRODUCTS_LIST_CACHE_TTL_SECONDS, json.dumps([p.model_dump(mode="json") for p in products]))
    except Exception as e:
        logger.warning(f"Redis cache write failed for products list: {e}")

    return products

@router.get("/search/semantic", response_model=List[schemas.Product])
@limiter.limit("20/minute")
async def search_products_semantic(
    request: Request,
    q: str,
    limit: int = 20,
    db: asyncpg.Connection = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")
    limit = max(1, min(limit, 50))
    return await semantic_search_products(db, redis_client, q.strip(), limit=limit)

@router.get("/{product_id}", response_model=schemas.Product)
async def read_product(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_product = await product_crud.get_product_by_id(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product


@router.post("/{product_id}/comments", response_model=schemas.Comment)
async def create_comment_for_product(product_id: int, comment: schemas.CommentCreate, db: asyncpg.Connection = Depends(get_db), current_user: dict = Depends(log_activity)):
    # Ensure the comment is for the correct product
    comment.product_id = product_id
    # Set user_name from current_user if not provided
    if not comment.user_name:
        comment.user_name = current_user.get('username', 'Anonymous')
    return await product_crud.create_comment(db, comment)

@router.get("/{product_id}/comments", response_model=List[schemas.Comment])
async def read_product_comments(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    return await product_crud.get_comments(db, product_id)

@router.put("/{product_id}/comments/{comment_id}", response_model=schemas.Comment)
async def update_product_comment(
    product_id: int,
    comment_id: int,
    comment_update: schemas.CommentUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(log_activity)
):
    # First, get the existing comment to check ownership
    existing_comment = await product_crud.get_comment_by_id(db, comment_id)
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if existing_comment.user_name != current_user.get('username') and not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized to update this comment")

    updated_comment = await product_crud.update_comment(db, comment_id, comment_update.content)
    if not updated_comment:
        raise HTTPException(status_code=500, detail="Failed to update comment")
    return updated_comment

@router.delete("/{product_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_comment(
    product_id: int,
    comment_id: int,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(log_activity)
):
    # First, get the existing comment to check ownership
    existing_comment = await product_crud.get_comment_by_id(db, comment_id)
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Check if the current user is the author of the comment or an admin
    if existing_comment.user_name != current_user.get('username') and not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    deleted = await product_crud.delete_comment(db, comment_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete comment")
    return

@router.get("/{product_id}/recommendations", response_model=List[schemas.Product])
async def get_product_recommendations(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    target_product = await product_crud.get_product_by_id(db, product_id=product_id)
    if target_product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    all_products = await product_crud.get_products(db)
    
    recommended_products = get_recommendations(target_product, all_products)
    
    if not recommended_products:
        # Optional: Return a default list of popular products or latest products if no specific recommendations are found
        # For now, we return an empty list.
        return []
    return recommended_products

async def run_csv_import_job(job_id: str, content: bytes, filename: str, redis_client: Redis):
    """Runs the actual CSV parsing/LLM-cleanup/DB-insert work outside the request
    lifecycle. Must acquire its own DB connection: the request's `db` dependency
    is released back to the pool before a BackgroundTask executes."""
    try:
        pool = await connection_pool.get_pool()
        async with pool.acquire() as db:
            result = await process_csv_and_save(content, filename, db)
        await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
        await set_job_status(redis_client, job_id, "completed", result)
    except ValueError as e:
        await set_job_status(redis_client, job_id, "failed", {"detail": str(e)})
    except Exception as e:
        logger.error(f"Failed to process CSV file {filename} (job {job_id}): {e}", exc_info=True)
        await set_job_status(redis_client, job_id, "failed", {"detail": "An unexpected error occurred during CSV processing."})

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def upload_products_from_csv(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    redis_client: Redis = Depends(get_redis_client),
    user=Depends(require_admin),
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    content = await file.read()
    job_id = str(uuid.uuid4())
    await set_job_status(redis_client, job_id, "processing")
    background_tasks.add_task(run_csv_import_job, job_id, content, file.filename, redis_client)
    return {"job_id": job_id, "status": "processing"}

@router.get("/upload/status/{job_id}")
@limiter.limit("60/minute")
async def get_csv_import_status(
    request: Request,
    job_id: str,
    redis_client: Redis = Depends(get_redis_client),
    user=Depends(require_admin),
):
    job = await get_job_status(redis_client, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return job
