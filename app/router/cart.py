from fastapi import APIRouter, Depends, HTTPException
from core.pkgs import database
from schemas.schemas import CartAdd, CartUpdate
from crud import cart as crud_cart
from crud.user import get_current_user, get_user_by_email
from redis.asyncio import Redis
from core.redis.redis_client import get_redis_client

router = APIRouter(prefix="/cart", tags=["cart"])

@router.get("/")
async def get_cart(db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), current_user: dict = Depends(get_current_user)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cart_items = await crud_cart.get_cart(db, user['id'], redis_client)
    return {"cart": cart_items}

@router.post("/add")
async def add_to_cart(data: CartAdd, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), current_user: dict = Depends(get_current_user)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await crud_cart.add_to_cart(db, user['id'], data.product_id, data.quantity, redis_client)
    return {"message": "Added to cart"}

@router.put("/update")
async def update_cart(data: CartUpdate, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), current_user: dict = Depends(get_current_user)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await crud_cart.update_cart(db, user['id'], data.product_id, data.quantity, redis_client)
    return {"message": "Cart updated"}

@router.delete("/remove")
async def remove_from_cart(product_id: int, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), current_user: dict = Depends(get_current_user)):
    user = await get_user_by_email(db, current_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await crud_cart.remove_from_cart(db, user['id'], product_id, redis_client)
    return {"message": "Removed from cart"}