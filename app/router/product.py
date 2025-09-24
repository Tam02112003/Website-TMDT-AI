from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from schemas import schemas
from crud import product as product_crud
from core.pkgs.database import get_db
import asyncpg
from typing import List
from services.CsvProcessingService import process_csv_and_save
from services.RecommendationService import get_recommendations
from core.app_config import logger
from core.redis.redis_client import get_redis_client
import json
from core.kafka.kafka_client import producer
from datetime import datetime
from typing import Optional
from core.dependencies import log_activity # Import log_activity for authentication
from crud.user import get_user_by_email, require_admin # Import for user and admin checks

router = APIRouter(prefix="/products", tags=["Products"])


# Add POST /products/ endpoint for creating a product
@router.post("/", response_model=schemas.Product)
async def create_product(product: schemas.ProductCreate, db: asyncpg.Connection = Depends(get_db)):
    new_product = await product_crud.create_product(db, product)
    if new_product is None:
        raise HTTPException(status_code=500, detail="Failed to create product")

    # Publish Kafka event for product creation
    event_data = {
        "product_id": new_product.id,
        "operation_type": "create",
        "timestamp": datetime.now().isoformat(),
        "product_data": json.loads(new_product.model_dump_json())
    }
    producer.send("product_events", json.dumps(event_data).encode('utf-8'))
    logger.info(f"Kafka event 'product_create' sent for product_id: {new_product.id}")

    return new_product

@router.get("/", response_model=List[schemas.Product])
async def read_products(skip: int = 0, limit: int = 100, search: Optional[str] = None, db: asyncpg.Connection = Depends(get_db)):
    products = await product_crud.get_products(db, skip=skip, limit=limit, search_query=search)
    return products

@router.get("/{product_id}", response_model=schemas.Product)
async def read_product(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_product = await product_crud.get_product_by_id(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product


# Add Update Product endpoint with Kafka publishing
@router.put("/{product_id}", response_model=schemas.Product)
async def update_product(product_id: int, product: schemas.ProductUpdate, db: asyncpg.Connection = Depends(get_db)):
    db_product = await product_crud.update_product(db, product_id, product)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Invalidate cache for deleted products
    redis_client = await get_redis_client()
    await redis_client.delete("deleted_products_cache")

    # Publish Kafka event
    event_data = {
        "product_id": product_id,
        "operation_type": "update",
        "timestamp": datetime.now().isoformat(),
         "new_data": json.loads(db_product.model_dump_json())
    }
    producer.send("product_events", json.dumps(event_data).encode('utf-8'))
    logger.info(f"Kafka event 'product_update' sent for product_id: {product_id}")

    return db_product

# Add Delete Product endpoint with Kafka publishing
@router.delete("/{product_id}", response_model=schemas.Product)
async def delete_product(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_product = await product_crud.delete_product(db, product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Invalidate cache for deleted products
    redis_client = await get_redis_client()
    await redis_client.delete("deleted_products_cache")

    # Publish Kafka event
    event_data = {
        "product_id": product_id,
        "operation_type": "delete",
        "timestamp": datetime.now().isoformat()
    }
    producer.send("product_events", json.dumps(event_data).encode('utf-8'))
    logger.info(f"Kafka event 'product_delete' sent for product_id: {product_id}")

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

        if existing_comment.user_name != current_user.get('username') and not current_user.get('is_admin'):        raise HTTPException(status_code=403, detail="Not authorized to update this comment")

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

@router.post("/upload")
async def upload_products_from_csv(file: UploadFile = File(...), db: asyncpg.Connection = Depends(get_db)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    try:
        result = await process_csv_and_save(file, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process CSV file {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during CSV processing.")
