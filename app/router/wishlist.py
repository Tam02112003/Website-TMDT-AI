from fastapi import APIRouter, Depends, HTTPException
from typing import List
import asyncpg
from schemas import schemas
from schemas.schemas import WishlistAdd
from crud import wishlist as crud_wishlist
from crud.user import get_user_by_email
from core.pkgs import database
from core.dependencies import log_activity

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("/", response_model=List[schemas.Product])
async def get_wishlist(db: asyncpg.Connection = Depends(database.get_db), current_user: dict = Depends(log_activity)):
    user = await get_user_by_email(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await crud_wishlist.get_wishlist(db, user["id"])


@router.get("/ids", response_model=List[int])
async def get_wishlist_ids(db: asyncpg.Connection = Depends(database.get_db), current_user: dict = Depends(log_activity)):
    """Lightweight endpoint for pages that only need to know which product ids
    are wishlisted (e.g. to render filled/outline heart icons on product
    cards) without fetching full product details for each one."""
    user = await get_user_by_email(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await crud_wishlist.get_wishlist_product_ids(db, user["id"])


@router.post("/add")
async def add_to_wishlist(data: WishlistAdd, db: asyncpg.Connection = Depends(database.get_db), current_user: dict = Depends(log_activity)):
    user = await get_user_by_email(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await crud_wishlist.add_to_wishlist(db, user["id"], data.product_id)
    return {"message": "Added to wishlist"}


@router.delete("/remove")
async def remove_from_wishlist(product_id: int, db: asyncpg.Connection = Depends(database.get_db), current_user: dict = Depends(log_activity)):
    user = await get_user_by_email(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await crud_wishlist.remove_from_wishlist(db, user["id"], product_id)
    return {"message": "Removed from wishlist"}
