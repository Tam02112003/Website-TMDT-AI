from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import httpx
import base64

from core.app_config import logger
from core.settings import settings
from core.limiter import limiter
from core.pkgs.database import get_db
from crud.product import get_product_by_id

EXTERNAL_TIMEOUT = httpx.Timeout(30.0)


class TryOnRequest(BaseModel):
    product_id: int
    user_image_base64: str


router = APIRouter(prefix="/tryon", tags=["tryon"])


@router.post("/")
@limiter.limit("5/minute")
async def tryon_endpoint(tryon_req: TryOnRequest, request: Request, db=Depends(get_db)):
    # Look up the product image server-side instead of trusting a client-supplied
    # URL - fetching an arbitrary attacker-controlled URL from the server would be
    # an SSRF vulnerability (e.g. probing internal services or cloud metadata).
    product = await get_product_by_id(db, tryon_req.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.image_urls:
        raise HTTPException(status_code=400, detail="This product has no image to try on")
    product_image_url = product.image_urls[0]

    try:
        header, base64_string = tryon_req.user_image_base64.split(',', 1) if ',' in tryon_req.user_image_base64 else ('', tryon_req.user_image_base64)
        user_image_bytes = base64.b64decode(base64_string)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}")

    headers = {
        "x-rapidapi-key": settings.RAPID_API.KEY.get_secret_value(),
        "x-rapidapi-host": "try-on-diffusion.p.rapidapi.com"
    }

    async with httpx.AsyncClient(timeout=EXTERNAL_TIMEOUT) as client:
        try:
            product_image_resp = await client.get(product_image_url)
            product_image_resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch product image {product_image_url}: {e}")
            raise HTTPException(status_code=502, detail="Could not fetch product image")

        files = {
            "clothing_image": ("product_image.jpeg", product_image_resp.content, "image/jpeg"),
            "avatar_image": ("user_avatar.jpeg", user_image_bytes, "image/jpeg"),
        }

        try:
            response = await client.post(
                "https://try-on-diffusion.p.rapidapi.com/try-on-file",
                files=files, headers=headers
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Try-on service timed out")
        except httpx.HTTPError as e:
            logger.error(f"Try-on API request failed: {e}")
            raise HTTPException(status_code=502, detail="Try-on service is unavailable")

    logger.info(f"External API response status: {response.status_code}")
    content_type = response.headers.get('content-type', '')

    if 'image' in content_type or (response.content and response.content[:2] == b'\xff\xd8'):
        base64_image = base64.b64encode(response.content).decode('utf-8')
        logger.info("Returning Base64 image result to frontend.")
        return {"result_image_url": f"data:{content_type or 'image/jpeg'};base64,{base64_image}"}

    try:
        json_response = response.json()
        logger.info(f"Returning JSON response from external API: {json_response}")
        return json_response
    except Exception:
        logger.error(f"External API returned unexpected non-JSON, non-image response: {response.text}")
        return {"error": "External API returned an unexpected response", "content": response.text, "status_code": response.status_code}
