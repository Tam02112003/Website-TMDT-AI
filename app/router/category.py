from fastapi import APIRouter, Depends, HTTPException
from schemas import schemas
from crud import category as category_crud
from core.pkgs.database import get_db
import asyncpg
from typing import List

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.post("/", response_model=schemas.Category)
async def create_category(category: schemas.CategoryCreate, db: asyncpg.Connection = Depends(get_db)):
    return await category_crud.create_category(db, category)

@router.get("/", response_model=List[schemas.Category])
async def read_categories(db: asyncpg.Connection = Depends(get_db)):
    return await category_crud.get_categories(db)

@router.get("/{category_id}", response_model=schemas.Category)
async def read_category(category_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_category = await category_crud.get_category_by_id(db, category_id=category_id)
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category

@router.put("/{category_id}", response_model=schemas.Category)
async def update_category(category_id: int, category: schemas.CategoryCreate, db: asyncpg.Connection = Depends(get_db)):
    db_category = await category_crud.update_category(db, category_id, category)
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category

@router.delete("/{category_id}", response_model=schemas.Category)
async def delete_category(category_id: int, db: asyncpg.Connection = Depends(get_db)):
    db_category = await category_crud.delete_category(db, category_id)
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category
