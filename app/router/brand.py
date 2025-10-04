from fastapi import APIRouter, Depends, HTTPException
from schemas import schemas
from crud import brand as brand_crud
from core.pkgs.database import get_db
import asyncpg
from typing import List

router = APIRouter(prefix="/brands", tags=["Brands"])

@router.post("/", response_model=schemas.Brand)
async def create_brand(brand: schemas.BrandCreate, db: asyncpg.Connection = Depends(get_db)):
    return await brand_crud.create_brand(db, brand)

@router.get("/", response_model=List[schemas.Brand])
async def read_brands(db: asyncpg.Connection = Depends(get_db)):
    return await brand_crud.get_brands(db)

@router.get("/{brand_id}", response_model=schemas.Brand)
async def read_brand(brand_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_brand = await brand_crud.get_brand_by_id(db, brand_id=brand_id)
    if db_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return db_brand

@router.put("/{brand_id}", response_model=schemas.Brand)
async def update_brand(brand_id: int, brand: schemas.BrandCreate, db: asyncpg.Connection = Depends(get_db)):
    db_brand = await brand_crud.update_brand(db, brand_id, brand)
    if db_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return db_brand

@router.delete("/{brand_id}", response_model=schemas.Brand)
async def delete_brand(brand_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_brand = await brand_crud.delete_brand(db, brand_id)
    if db_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return db_brand
