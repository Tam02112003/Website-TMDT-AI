from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy.orm import Session
from schemas import schemas
from crud import news
from core.pkgs import database
from crud.user import require_admin
from core.redis.redis_client import get_redis_client
from core.kafka.kafka_client import producer
import json
from services.NewsAIService import generate_news_content
from schemas.schemas import AINewsGenerateRequest

router = APIRouter(prefix="/news", tags=["news"])

@router.get("/", response_model=list[schemas.News])
async def read_news(skip: int = 0, limit: int = 100, search: Optional[str] = None, db: Session = Depends(database.get_db), redis_client: Redis = Depends(get_redis_client)):
    cache_key = f"news:{skip}:{limit}:{search}"
    cached = await redis_client.get(cache_key)
    if cached:
        return [schemas.News(**p) for p in json.loads(cached)]
    result = await news.get_news(db, skip=skip, limit=limit, search_query=search)
    await redis_client.setex(cache_key, 60, json.dumps([r.model_dump(mode='json') for r in result]))
    return result


@router.get("/{news_id}", response_model=schemas.News)
async def read_news_item(news_id: int, db: Session = Depends(database.get_db)):
    db_news = await news.get_news_item(db, news_id)
    if not db_news:
        raise HTTPException(status_code=404, detail="News not found")
    return db_news

@router.post("/", response_model=schemas.News)
async def create_news(news_data: schemas.NewsCreate, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    result = await news.create_news(db, news_data)
    producer.send('news', json.dumps({"action": "create", "title": news_data.title, "user": user.get("username")}).encode())
    return result

@router.put("/{news_id}", response_model=schemas.News)
async def update_news(news_id: int, news_data: schemas.NewsUpdate, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    db_news = await news.update_news(db, news_id, news_data)
    if not db_news:
        raise HTTPException(status_code=404, detail="News not found")
    return db_news

@router.delete("/{news_id}", response_model=schemas.News)
async def delete_news(news_id: int, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    db_news = await news.delete_news(db, news_id)
    if not db_news:
        raise HTTPException(status_code=404, detail="News not found")
    return db_news


@router.post("/{news_id}/restore", response_model=schemas.News)
async def restore_news(news_id: int, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    db_news = await news.restore_news(db, news_id)
    if not db_news:
        raise HTTPException(status_code=404, detail="News not found or cannot be restored")
    return db_news

@router.post("/generate_ai", response_model=schemas.News)
async def generate_ai_news(request_data: AINewsGenerateRequest, db: Session = Depends(database.get_db), user=Depends(require_admin)):
    try:
        generated_content = await generate_news_content(
            topic=request_data.topic,
            keywords=request_data.keywords,
            length=request_data.length
        )
        
        # Use a generic Cloudinary placeholder URL since AI doesn't generate images
        generic_cloudinary_placeholder_url = "https://res.cloudinary.com/demo/image/upload/w_300,h_200,c_fill/sample.jpg"

        news_create_data = schemas.NewsCreate(
            title=generated_content["title"],
            content=generated_content["content"],
            image_url=generic_cloudinary_placeholder_url, 
            is_active=True # AI generated news can be active by default or set to False for review
        )
        
        created_news = await news.create_news(db, news_create_data)
        producer.send('news', json.dumps({"action": "create_ai", "title": created_news.title, "user": user.get("username")}).encode())
        return created_news
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate and save AI news: {e}")
