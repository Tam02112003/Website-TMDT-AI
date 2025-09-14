from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import Response
import requests
import os
from core.settings import settings
router = APIRouter(prefix="/tryon", tags=["tryon"])

@router.post("/upload")
def tryon(
    clothing_image: UploadFile = File(None),
    clothing_prompt: str = Form(None),
    avatar_image: UploadFile = File(None),
    avatar_sex: str = Form(None),
    avatar_prompt: str = Form(None),
    background_image: UploadFile = File(None),
    background_prompt: str = Form(None),
    seed: str = Form(None)
):
    url = "https://try-on-diffusion.p.rapidapi.com/try-on-file"
    files = {}
    if clothing_image:
        files["clothing_image"] = (clothing_image.filename, clothing_image.file, clothing_image.content_type)
    if avatar_image:
        files["avatar_image"] = (avatar_image.filename, avatar_image.file, avatar_image.content_type)
    if background_image:
        files["background_image"] = (background_image.filename, background_image.file, background_image.content_type)
    data = {}
    if clothing_prompt:
        data["clothing_prompt"] = clothing_prompt
    if avatar_sex:
        data["avatar_sex"] = avatar_sex
    if avatar_prompt:
        data["avatar_prompt"] = avatar_prompt
    if background_prompt:
        data["background_prompt"] = background_prompt
    if seed:
        data["seed"] = seed
    headers = {
        "x-rapidapi-key": settings.RAPID_API.KEY.get_secret_value(),
        "x-rapidapi-host": "try-on-diffusion.p.rapidapi.com"
    }
    response = requests.post(url, files=files, data=data, headers=headers)
    content_type = response.headers.get('content-type', '')
    # Always return image as bytes if response is binary
    if 'image' in content_type or (response.content and response.content[:2] == b'\xff\xd8'):
        return Response(content=response.content, media_type=content_type or 'image/jpeg')
    try:
        return response.json()
    except Exception:
        return {"error": "Invalid JSON response", "content": response.text, "status_code": response.status_code}
