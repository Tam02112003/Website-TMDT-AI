from fastapi import APIRouter, Response, HTTPException, Request
from pydantic import BaseModel
import requests
import base64
from io import BytesIO

from core.app_config import logger
from core.settings import settings
from core.limiter import limiter  # Import the limiter

class TryOnRequest(BaseModel):
    product_image_url: str
    user_image_base64: str

router = APIRouter(prefix="/tryon", tags=["tryon"])

@router.post("/")
@limiter.limit("5/minute")  # Apply the rate limit
async def tryon_endpoint(tryon_req: TryOnRequest, request: Request):
    # Decode base64 user image
    try:
        # Remove data:image/jpeg;base64, prefix if present
        header, base64_string = tryon_req.user_image_base64.split(',', 1) if ',' in tryon_req.user_image_base64 else ('', tryon_req.user_image_base64)
        user_image_bytes = base64.b64decode(base64_string)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}")

    url = "https://try-on-diffusion.p.rapidapi.com/try-on-file"
    files = {
        "clothing_image": ("product_image.jpeg", BytesIO(requests.get(tryon_req.product_image_url).content), 'image/jpeg'),
        "avatar_image": ("user_avatar.jpeg", BytesIO(user_image_bytes), 'image/jpeg')
    }
    data = {}
    headers = {
        "x-rapidapi-key": settings.RAPID_API.KEY.get_secret_value(),
        "x-rapidapi-host": "try-on-diffusion.p.rapidapi.com"
    }
    response = requests.post(url, files=files, data=data, headers=headers)
    logger.info(f"External API response status: {response.status_code}")
    logger.info(f"External API response content-type: {response.headers.get('content-type')}")

    content_type = response.headers.get('content-type', '')
    # Always return image as bytes if response is binary
    if 'image' in content_type or (response.content and response.content[:2] == b'\xff\xd8'):
        # Convert image bytes to base64 and return as JSON
        base64_image = base64.b64encode(response.content).decode('utf-8')
        final_response = {"result_image_url": f"data:{content_type or 'image/jpeg'};base64,{base64_image}"}
        logger.info("Returning Base64 image result to frontend.")
        return final_response
    try:
        # If not an image, try to parse as JSON (e.g., for error messages from external API)
        json_response = response.json()
        logger.info(f"Returning JSON response from external API: {json_response}")
        return json_response
    except Exception:
        # Fallback for non-image, non-JSON responses
        logger.error(f"External API returned unexpected non-JSON, non-image response: {response.text}")
        return {"error": "External API returned an unexpected response", "content": response.text, "status_code": response.status_code}
