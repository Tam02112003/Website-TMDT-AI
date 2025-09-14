from fastapi import APIRouter, Depends, HTTPException, status
from core.redis.redis_client import clear_redis_cache_data
from crud.user import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/clear-redis-cache", summary="Clear Redis Cache (Admin Only)")
async def clear_redis_cache(
    current_user: dict = Depends(require_admin)
):
    """
    Clears all data from the Redis cache.
    This operation should only be performed by authorized administrators.
    """
    try:
        await clear_redis_cache_data()
        return {"message": "Redis cache cleared successfully.", "admin": current_user["username"]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear Redis cache: {e}"
        )
