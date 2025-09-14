from fastapi import APIRouter, Depends, HTTPException
from schemas import schemas
from core.pkgs import database
import asyncpg
from services import ChatbotServices
from redis.asyncio import Redis
from core.redis.redis_client import get_redis_client
from core.app_config import logger

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

@router.post("/", response_model=schemas.ChatbotResponse)
async def chat_with_bot(request: schemas.ChatbotRequest, db: asyncpg.Connection = Depends(database.get_db), redis_client: Redis = Depends(get_redis_client)):
    try:
        logger.info(f"Received chatbot request for session: {request.session_id}")
        response = await ChatbotServices.get_chatbot_response(request.question, db, redis_client, request.session_id)
        return response
    except Exception as e:
        logger.error(f"Error in chatbot endpoint for session {request.session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred in the chatbot.")