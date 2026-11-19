from fastapi import APIRouter, Depends, HTTPException, Request
from schemas import schemas
from core.pkgs import database
import asyncpg
from services import ChatbotServices
from redis.asyncio import Redis
from core.redis.redis_client import get_redis_client
from core.app_config import logger
from core.limiter import limiter
from crud.user import get_optional_user

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

@router.post("/", response_model=schemas.ChatbotResponse)
@limiter.limit("20/minute")
async def chat_with_bot(
    request: Request,
    body: schemas.ChatbotRequest,
    db: asyncpg.Connection = Depends(database.get_db),
    redis_client: Redis = Depends(get_redis_client),
    user: dict = Depends(get_optional_user),
):
    try:
        logger.info(f"Received chatbot request for session: {body.session_id}, user: {user.get('sub') if user else 'anonymous'}")
        response = await ChatbotServices.get_chatbot_response(body.question, db, redis_client, body.session_id, user)
        return response
    except Exception as e:
        logger.error(f"Error in chatbot endpoint for session {body.session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred in the chatbot.")