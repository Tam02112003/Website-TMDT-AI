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
async def read_products(skip: int = 0, limit: int = 100, db: asyncpg.Connection = Depends(get_db)):
    products = await product_crud.get_products(db, skip=skip, limit=limit)
    return products

@router.get("/{product_id}", response_model=schemas.Product)
async def read_product(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_product = await product_crud.get_product(db, product_id=product_id)
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

# Add Get Deleted Products endpoint with Redis caching
@router.get("/deleted/", response_model=List[schemas.Product])
async def read_deleted_products(skip: int = 0, limit: int = 100, db: asyncpg.Connection = Depends(get_db)):
    redis_client = await get_redis_client()
    cache_key = f"deleted_products_cache:skip_{skip}:limit_{limit}"
    
    cached_products = await redis_client.get(cache_key)
    if cached_products:
        logger.info("Serving deleted products from Redis cache.")
        return [schemas.Product.model_validate(json.loads(p)) for p in json.loads(cached_products)]

    products = await product_crud.get_deleted_products(db, skip=skip, limit=limit)
    
    # Store in cache (serialize Pydantic models to JSON strings)
    await redis_client.set(cache_key, json.dumps([p.model_dump_json() for p in products]), ex=3600) # Cache for 1 hour
    
    return products

# Add Restore Product endpoint with Kafka publishing
@router.post("/{product_id}/restore", response_model=schemas.Product)
async def restore_product(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_product = await product_crud.restore_product(db, product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found or already active")
    
    # Invalidate cache for deleted products
    redis_client = await get_redis_client()
    await redis_client.delete("deleted_products_cache")

    # Publish Kafka event
    event_data = {
        "product_id": product_id,
        "operation_type": "restore",
        "timestamp": datetime.now().isoformat()
    }
    producer.send("product_events", json.dumps(event_data).encode('utf-8'))
    logger.info(f"Kafka event 'product_restore' sent for product_id: {product_id}")

    return db_product

@router.post("/{product_id}/comments", response_model=schemas.Comment)
async def create_comment_for_product(product_id: int, comment: schemas.CommentCreate, db: asyncpg.Connection = Depends(get_db)):
    # Ensure the comment is for the correct product
    comment.product_id = product_id
    return await product_crud.create_comment(db, comment)

@router.get("/{product_id}/comments", response_model=List[schemas.Comment])
async def read_product_comments(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    return await product_crud.get_comments(db, product_id)

@router.get("/{product_id}/recommendations", response_model=List[schemas.Product])
async def get_product_recommendations(product_id: int, db: asyncpg.Connection = Depends(get_db)):
    target_product = await product_crud.get_product(db, product_id=product_id)
    if target_product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    all_products = await product_crud.get_all_products(db)
    
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
