from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import httpx
from redis.asyncio import Redis
from core.redis.redis_client import clear_redis_cache_data, get_redis_client, invalidate_cache_pattern
from router.product import PRODUCTS_LIST_CACHE_PATTERN
from crud import user as crud_user
from crud import order as crud_order
from crud import news as crud_news
from crud import product as crud_product
from crud import discount as crud_discount
from core.pkgs import database
from crud.user import require_admin
from schemas.schemas import UserUpdate, NewsCreate, NewsUpdate, ProductCreate, ProductUpdate, AINewsGenerateRequest, AINewsGenerateResponse, DiscountCreate, DiscountUpdate, ProductResearchRequest, ProductResearchResponse
from services import NewsAIService
from services import ProductResearchService
from services import BackupService
from core.settings import settings
from typing import Optional
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

@router.post("/backup", summary="Export DB and upload to Google Drive (Admin Only)")
async def create_backup_endpoint(db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    try:
        return await BackupService.create_and_upload_backup(db)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Backup failed: {e}")

@router.get("/backup/authorize", summary="One-time: start Google OAuth consent for Drive backups")
async def backup_authorize():
    # Service accounts can't write to a personal Drive folder's quota - uploads
    # must run as the folder's real owner. This is a one-time bootstrap link an
    # admin opens directly in a browser (plain navigation can't carry our own
    # Bearer token, so it isn't gated by require_admin like the rest of this
    # router - see the commit message for why that's an acceptable tradeoff
    # here), not a feature exposed anywhere in the admin UI.
    if not settings.GDRIVE_BACKUP.OAUTH_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="GDRIVE_BACKUP_OAUTH_REDIRECT_URI is not configured.")
    params = {
        "client_id": settings.GOOGLE.CLIENT_ID,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive.file",
        "redirect_uri": settings.GDRIVE_BACKUP.OAUTH_REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent",
    }
    async with httpx.AsyncClient() as client:
        request = client.build_request("GET", settings.GOOGLE.OAUTH2_URL, params=params)
        return RedirectResponse(str(request.url))

@router.get("/backup/oauth-callback", summary="One-time: Google OAuth callback for Drive backup setup")
async def backup_oauth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    data = {
        "code": code,
        "client_id": settings.GOOGLE.CLIENT_ID,
        "client_secret": settings.GOOGLE.CLIENT_SECRET.get_secret_value(),
        "redirect_uri": settings.GDRIVE_BACKUP.OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(settings.GOOGLE.TOKEN_URL, data=data)
    token_json = token_resp.json()
    refresh_token = token_json.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "No refresh_token returned - Google only issues one on the first consent. "
                "Revoke prior access at https://myaccount.google.com/permissions (find this "
                "app, remove it) and visit /admin/backup/authorize again. "
                f"Raw response: {token_json}"
            ),
        )
    return {
        "message": "Copy this refresh_token into the GDRIVE_BACKUP_REFRESH_TOKEN env var and redeploy. Shown only once.",
        "refresh_token": refresh_token,
    }

@router.get("/users", summary="Get all users (Admin Only)")
async def get_all_users_endpoint(db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    users = await crud_user.get_all_users(db)
    return users

@router.put("/users/{user_id}", summary="Update user (Admin Only)")
async def update_user_endpoint(user_id: int, user_data: UserUpdate, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    updated_user = await crud_user.update_user(db, user_id, user_data.username, user_data.email, user_data.is_admin)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.delete("/users/{user_id}", summary="Delete user (Admin Only)")
async def delete_user_endpoint(user_id: int, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    success = await crud_user.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

@router.get("/all_orders", summary="Get all orders (Admin Only)")
async def get_all_orders_endpoint(search: Optional[str] = None, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    orders = await crud_order.get_all_orders(db, search_query=search)
    return {"orders": orders}

@router.post("/news", summary="Create news (Admin Only)")
async def create_news_endpoint(news: NewsCreate, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    created_news = await crud_news.create_news(db, news)
    return created_news

@router.get("/news", summary="Get all news (Admin Only)")
async def get_all_news_endpoint(search: Optional[str] = None, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    all_news = await crud_news.get_news(db, skip=0, limit=100, search_query=search) # Assuming get_news fetches all news for admin
    return all_news

@router.get("/news/deleted", summary="Get all deleted news (Admin Only)")
async def get_deleted_news_endpoint(db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    deleted_news = await crud_news.get_deleted_news(db)
    return deleted_news

@router.put("/news/{news_id}/restore", summary="Restore a news item (Admin Only)")
async def restore_news_endpoint(news_id: int, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    restored_news = await crud_news.restore_news(db, news_id)
    if not restored_news:
        raise HTTPException(status_code=404, detail="News not found or already active")
    return restored_news

@router.get("/news/{news_id}", summary="Get news by ID (Admin Only)")
async def get_news_by_id_endpoint(news_id: int, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    news_item = await crud_news.get_news_item(db, news_id)
    if not news_item:
        raise HTTPException(status_code=404, detail="News not found")
    return news_item

@router.put("/news/{news_id}", summary="Update news (Admin Only)")
async def update_news_endpoint(news_id: int, news: NewsUpdate, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    updated_news = await crud_news.update_news(db, news_id, news)
    if not updated_news:
        raise HTTPException(status_code=404, detail="News not found")
    return updated_news

@router.delete("/news/{news_id}", summary="Delete news (Admin Only)")
async def delete_news_endpoint(news_id: int, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    deleted_news = await crud_news.delete_news(db, news_id)
    if not deleted_news:
        raise HTTPException(status_code=404, detail="News not found")
    return {"message": "News deleted successfully"}

@router.post("/products", summary="Create product (Admin Only)")
async def create_product_endpoint(product: ProductCreate, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    created_product = await crud_product.create_product(db, product)
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return created_product

@router.get("/products", summary="Get all products (Admin Only)")
async def get_all_products_endpoint(search: Optional[str] = None, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    all_products = await crud_product.get_products(db, search_query=search)
    return all_products

@router.get("/products/deleted", summary="Get all deleted products (Admin Only)")
async def get_deleted_products_endpoint(db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    deleted_products = await crud_product.get_deleted_products(db)
    return deleted_products

@router.get("/products/pending-ai", summary="Get AI-researched products awaiting review (Admin Only)")
async def get_pending_ai_products_endpoint(db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    return await crud_product.get_pending_ai_products(db)

@router.put("/products/{product_id}/restore", summary="Restore a product (Admin Only)")
async def restore_product_endpoint(product_id: int, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    restored_product = await crud_product.restore_product(db, product_id)
    if not restored_product:
        raise HTTPException(status_code=404, detail="Product not found or already active")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return restored_product

@router.get("/products/{product_id}", summary="Get product by ID (Admin Only)")
async def get_product_by_id_endpoint(product_id: int, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    product_item = await crud_product.get_product_by_id(db, product_id)
    if not product_item:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_item

@router.put("/products/{product_id}", summary="Update product (Admin Only)")
async def update_product_endpoint(product_id: int, product: ProductUpdate, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    updated_product = await crud_product.update_product(db, product_id, product)
    if not updated_product:
        raise HTTPException(status_code=404, detail="Product not found")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return updated_product

@router.delete("/products/{product_id}", summary="Delete product (Admin Only)")
async def delete_product_endpoint(product_id: int, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    deleted_product = await crud_product.delete_product(db, product_id)
    if not deleted_product:
        raise HTTPException(status_code=404, detail="Product not found")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return {"message": "Product deleted successfully"}

@router.post("/news/generate-ai", summary="Generate news content using AI (Admin Only)", response_model=AINewsGenerateResponse)
async def generate_ai_news_endpoint(request: AINewsGenerateRequest, admin: dict = Depends(require_admin)):
    try:
        generated_content = await NewsAIService.generate_news_content(
            topic=request.topic,
            keywords=request.keywords,
            length=request.length
        )
        return generated_content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI news generation failed: {e}")

@router.post("/products/research", summary="Research real product candidates using AI (Admin Only)", response_model=ProductResearchResponse)
async def research_products_endpoint(request: ProductResearchRequest, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    try:
        result = await ProductResearchService.research_product_candidates(
            db=db, topic=request.topic, keywords=request.keywords
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI product research failed: {e}")

@router.post("/discounts", summary="Create discount (Admin Only)")
async def create_discount_endpoint(discount: DiscountCreate, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    created_discount = await crud_discount.create_discount(db, discount)
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return created_discount

@router.get("/discounts", summary="Get all discounts (Admin Only)")
async def get_all_discounts_endpoint(db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    all_discounts = await crud_discount.get_discounts(db, skip=0, limit=100) # Assuming get_discounts fetches all discounts for admin
    return all_discounts

@router.get("/discounts/deleted", summary="Get all deleted discounts (Admin Only)")
async def get_deleted_discounts_endpoint(db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    deleted_discounts = await crud_discount.get_deleted_discounts(db)
    return deleted_discounts

@router.put("/discounts/{discount_id}/restore", summary="Restore a discount (Admin Only)")
async def restore_discount_endpoint(discount_id: int, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    restored_discount = await crud_discount.restore_discount(db, discount_id)
    if not restored_discount:
        raise HTTPException(status_code=404, detail="Discount not found or already active")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return restored_discount

@router.get("/discounts/{discount_id}", summary="Get discount by ID (Admin Only)")
async def get_discount_by_id_endpoint(discount_id: int, db=Depends(database.get_db), admin: dict = Depends(require_admin)):
    discount_item = await crud_discount.get_discount(db, discount_id)
    if not discount_item:
        raise HTTPException(status_code=404, detail="Discount not found")
    return discount_item

@router.put("/discounts/{discount_id}", summary="Update discount (Admin Only)")
async def update_discount_endpoint(discount_id: int, discount: DiscountUpdate, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    updated_discount = await crud_discount.update_discount(db, discount_id, discount)
    if not updated_discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return updated_discount

@router.delete("/discounts/{discount_id}", summary="Delete discount (Admin Only)")
async def delete_discount_endpoint(discount_id: int, db=Depends(database.get_db), redis_client: Redis = Depends(get_redis_client), admin: dict = Depends(require_admin)):
    deleted_discount = await crud_discount.delete_discount(db, discount_id)
    if not deleted_discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    await invalidate_cache_pattern(redis_client, PRODUCTS_LIST_CACHE_PATTERN)
    return {"message": "Discount deleted successfully"}
