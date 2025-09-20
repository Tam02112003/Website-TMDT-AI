from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy.orm import Session
from schemas import schemas
from crud import discount
from core.pkgs import database
from crud.user import require_admin
from core.redis.redis_client import get_redis_client
from core.kafka.kafka_client import producer
import json

router = APIRouter(prefix="/discounts", tags=["discounts"])

@router.get("/", response_model=list[schemas.Discount])
async def read_discounts(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db), redis_client: Redis = Depends(get_redis_client)):
    cache_key = f"discounts:{skip}:{limit}"
    cached = await redis_client.get(cache_key)
    if cached:
        return [schemas.Discount(**p) for p in json.loads(cached)]
    result = await discount.get_discounts(db, skip=skip, limit=limit)
    await redis_client.setex(cache_key, 60, json.dumps([r.model_dump(mode='json') for r in result]))
    return result


@router.get("/{discount_id}", response_model=schemas.Discount)
async def read_discount(discount_id: int, db: Session = Depends(database.get_db)):
    db_discount = await discount.get_discount(db, discount_id)
    if not db_discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    return db_discount

@router.post("/", response_model=schemas.Discount)
async def create_discount(discount_data: schemas.DiscountCreate, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    result = await discount.create_discount(db, discount_data)
    producer.send('discounts', json.dumps({"action": "create", "name": discount_data.name, "user": user.get("username")}).encode())
    return result

@router.put("/{discount_id}", response_model=schemas.Discount)
async def update_discount(discount_id: int, discount_data: schemas.DiscountUpdate, db: Session = Depends(
    database.get_db), user=Depends(require_admin)):
    db_discount = await discount.update_discount(db, discount_id, discount_data)
    if not db_discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    return db_discount

@router.delete("/{discount_id}", response_model=schemas.Discount)
async def delete_discount(discount_id: int, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    db_discount = await discount.delete_discount(db, discount_id)
    if not db_discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    return db_discount


@router.post("/{discount_id}/restore", response_model=schemas.Discount)
async def restore_discount(discount_id: int, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    db_discount = await discount.restore_discount(db, discount_id)
    if not db_discount:
        raise HTTPException(status_code=404, detail="Discount not found or cannot be restored")
    return db_discount
