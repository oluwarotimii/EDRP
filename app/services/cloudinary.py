import os
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException, status
import logging
from app.config import settings

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

logger = logging.getLogger(__name__)

async def upload_image_to_cloudinary(file: UploadFile, folder: str = "school_erp") -> str:
    """
    Upload an image file to Cloudinary and return the URL.
    
    Args:
        file: The image file to upload
        folder: The Cloudinary folder to upload to
        
    Returns:
        The URL of the uploaded image
        
    Raises:
        HTTPException: If the upload fails
    """
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        logger.error("Cloudinary credentials not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File upload service is not configured"
        )
    
    # Check file type
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Must be one of: {', '.join(allowed_extensions)}"
        )
    
    # Read file content
    contents = await file.read()
    
    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="image",
            eager=[{"width": 500, "crop": "scale"}],  # Generate a scaled version
            public_id=f"{folder}_{file.filename}_{int(datetime.now().timestamp())}",
        )
        
        # Return the secure URL
        return result["secure_url"]
    
    except Exception as e:
        logger.error(f"Error uploading to Cloudinary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )
    finally:
        # Reset file pointer for potential further processing
        await file.seek(0)

async def delete_image_from_cloudinary(public_id: str) -> bool:
    """
    Delete an image from Cloudinary by its public ID.
    
    Args:
        public_id: The public ID of the image to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception as e:
        logger.error(f"Error deleting from Cloudinary: {str(e)}")
        return False
