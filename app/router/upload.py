from fastapi import APIRouter, File, UploadFile, HTTPException, status, Query
from services.CloudinaryService import upload_image_from_bytes, get_image_url, delete_image
from core.app_config import logger
import cloudinary.api
from starlette.concurrency import run_in_threadpool
from typing import List
from pydantic import BaseModel

class DeleteImagesRequest(BaseModel):
    public_ids: List[str]

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("/image")
async def upload_single_image(file: UploadFile = File(...)):
    try:
        # Validate file type (optional but recommended)
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Only images are allowed.")

        # Read file content into memory
        contents = await file.read()

        # Upload to Cloudinary
        image_url = await upload_image_from_bytes(contents, folder="manual_uploads")

        return {"message": "Image uploaded successfully", "url": image_url}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error uploading image: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload image: {e}")

@router.get("/image/{public_id}")
async def get_uploaded_image_url(public_id: str):
    try:
        image_url = await get_image_url(public_id)
        if not image_url:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
        return {"public_id": public_id, "url": image_url}
    except Exception as e:
        logger.error(f"Error retrieving image URL for {public_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve image URL: {e}")

@router.delete("/image/{public_id:path}")
async def delete_uploaded_image(public_id: str):
    try:
        # Cloudinary API destroy is synchronous, run in thread pool
        result = await run_in_threadpool(delete_image, public_id)
        return {"message": "Image deleted successfully", "public_id": public_id, "result": result}
    except RuntimeError as re:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(re))
    except Exception as e:
        logger.error(f"Error deleting image {public_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete image: {e}")

@router.post("/delete-multiple")
async def delete_multiple_images(request: DeleteImagesRequest):
    results = []
    errors = []
    for public_id in request.public_ids:
        try:
            result = await run_in_threadpool(delete_image, public_id)
            results.append({"public_id": public_id, "status": "success", "result": result})
        except Exception as e:
            logger.error(f"Error deleting image {public_id}: {e}", exc_info=True)
            errors.append({"public_id": public_id, "status": "failed", "error": str(e)})
    
    if errors:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"message": "Some images failed to delete", "errors": errors, "successes": results})
    
    return {"message": "All selected images deleted successfully", "results": results}

@router.get("/images")
async def list_uploaded_images(folder: str = Query(None, description="List images within a specific folder")):
    try:
        options = {'type': 'upload', 'max_results': 500} # Max 500 results per call
        if folder:
            options['prefix'] = folder
        
        # Cloudinary API calls are synchronous, so run in a thread pool
        resources = await run_in_threadpool(cloudinary.api.resources, **options)
        
        image_list = []
        for resource in resources.get('resources', []):
            image_list.append({
                "public_id": resource.get('public_id'),
                "url": resource.get('secure_url'),
                "folder": resource.get('folder')
            })
        return image_list
    except Exception as e:
        logger.error(f"Error listing images from Cloudinary: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to list images: {e}")
