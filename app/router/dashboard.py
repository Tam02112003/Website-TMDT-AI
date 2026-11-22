from fastapi import APIRouter, Depends
from redis.asyncio import Redis
import json
import asyncpg
from schemas import schemas
from crud import dashboard as dashboard_crud
from core.pkgs.database import get_db
from crud.user import require_admin
from core.redis.redis_client import get_redis_client
from core.app_config import logger

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])

DASHBOARD_CACHE_TTL_SECONDS = 60


@router.get("/", response_model=schemas.DashboardResponse)
async def get_dashboard(
    days: int = 30,
    db: asyncpg.Connection = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    admin: dict = Depends(require_admin),
):
    days = max(1, min(days, 365))
    cache_key = f"admin:dashboard:{days}"

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return schemas.DashboardResponse(**json.loads(cached))
    except Exception as e:
        logger.warning(f"Redis cache read failed for admin dashboard, falling back to DB: {e}")

    response = schemas.DashboardResponse(
        summary=await dashboard_crud.get_summary(db, days),
        revenue_timeseries=await dashboard_crud.get_revenue_timeseries(db, days),
        top_products=await dashboard_crud.get_top_products(db, days),
        order_status_breakdown=await dashboard_crud.get_order_status_breakdown(db),
        recent_orders=await dashboard_crud.get_recent_orders(db),
    )

    try:
        await redis_client.setex(cache_key, DASHBOARD_CACHE_TTL_SECONDS, response.model_dump_json())
    except Exception as e:
        logger.warning(f"Redis cache write failed for admin dashboard: {e}")

    return response
