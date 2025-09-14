from typing import Optional

import cloudinary
import cloudinary.uploader
import cloudinary.api
from core.settings import settings
from core.app_config import logger

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY.CLOUD_NAME,
    api_key=settings.CLOUDINARY.API_KEY,
    api_secret=settings.CLOUDINARY.API_SECRET.get_secret_value()
)

def get_public_id_from_url(image_url: str) -> Optional[str]:
    """
    Extracts the public ID from a Cloudinary image URL.
    Assumes the URL format is consistent (e.g., .../upload/v<version>/<public_id>.<extension>)
    """
    try:
        # Example URL: https://res.cloudinary.com/image/upload/v1234567890/folder/subfolder/image_name.jpg
        # We want 'folder/subfolder/image_name'
        parts = image_url.split("/upload/")
        if len(parts) < 2:
            return None
        
        path_with_version = parts[1]
        # Remove version number (e.g., v1234567890/)
        path_parts = path_with_version.split("/", 1)
        if len(path_parts) < 2:
            return None
        
        public_id_with_extension = path_parts[1]
        public_id = public_id_with_extension.rsplit(".", 1)[0] # Remove extension
        return public_id
    except Exception as e:
        logger.warning(f"Could not extract public ID from URL {image_url}: {e}")
        return None

async def get_image_info(identifier: str) -> Optional[dict]:
    """
    Retrieves information about an image from Cloudinary.
    The identifier can be a public ID or a full Cloudinary URL.
    """
    public_id = identifier
    if identifier.startswith("http"):
        public_id = get_public_id_from_url(identifier)
        if not public_id:
            logger.warning(f"Invalid Cloudinary URL provided: {identifier}")
            return None

    try:
        logger.debug(f"Attempting to fetch Cloudinary resource with public_id: '{public_id}'")
        resource = cloudinary.api.resource(public_id)
        return resource
    except cloudinary.api.NotFound:
        logger.info(f"Image with public ID '{public_id}' not found in Cloudinary.")
        return None
    except Exception as e:
        logger.error(f"Error fetching image info for '{public_id}': {e}", exc_info=True)
        return None

async def check_image_exists(identifier: str) -> bool:
    """
    Checks if an image exists in Cloudinary.
    The identifier can be a public ID or a full Cloudinary URL.
    """
    return await get_image_info(identifier) is not None

async def get_image_url(identifier: str) -> Optional[str]:
    """
    Retrieves the secure URL of an image from Cloudinary.
    The identifier can be a public ID or a full Cloudinary URL.
    """
    info = await get_image_info(identifier)
    return info.get('secure_url') if info else None

async def upload_image(file_path: str, folder: str = "news_images") -> str:
    """
    Uploads an image to Cloudinary and returns its public URL.
    :param file_path: Path to the image file.
    :param folder: The folder in Cloudinary to upload the image to.
    :return: Public URL of the uploaded image.
    """
    try:
        logger.info(f"Uploading image {file_path} to Cloudinary folder {folder}...")
        upload_result = cloudinary.uploader.upload(file_path, folder=folder)
        logger.info(f"Image uploaded successfully: {upload_result['secure_url']}")
        return upload_result['secure_url']
    except Exception as e:
        logger.error(f"Failed to upload image to Cloudinary: {e}", exc_info=True)
        raise RuntimeError(f"Cloudinary upload failed: {e}")

async def upload_image_from_bytes(image_bytes: bytes, folder: str = "news_images") -> str:
    """
    Uploads an image from bytes to Cloudinary and returns its public URL.
    :param image_bytes: Image data as bytes.
    :param folder: The folder in Cloudinary to upload the image to.
    :return: Public URL of the uploaded image.
    """
    try:
        logger.info(f"Uploading image from bytes to Cloudinary folder {folder}...")
        upload_result = cloudinary.uploader.upload(image_bytes, folder=folder)
        logger.info(f"Image uploaded successfully: {upload_result['secure_url']}")
        return upload_result['secure_url']
    except Exception as e:
        logger.error(f"Failed to upload image from bytes to Cloudinary: {e}", exc_info=True)
        raise RuntimeError(f"Cloudinary upload failed: {e}")

def delete_image(public_id: str) -> dict:
    """
    Deletes an image from Cloudinary using its public ID.
    :param public_id: The public ID of the image to delete.
    :return: The result of the deletion operation.
    """
    try:
        logger.info(f"Attempting to delete image with public ID: {public_id}")
        destroy_result = cloudinary.uploader.destroy(public_id)
        logger.info(f"Image deletion result for {public_id}: {destroy_result}")
        if destroy_result.get('result') == 'ok':
            return {"message": "Image deleted successfully", "result": destroy_result}
        else:
            logger.error(f"Failed to delete image {public_id}: {destroy_result}")
            raise RuntimeError(f"Cloudinary deletion failed: {destroy_result.get('result', 'unknown error')}")
    except Exception as e:
        logger.error(f"Error deleting image {public_id}: {e}", exc_info=True)
        raise RuntimeError(f"Cloudinary deletion failed: {e}")
