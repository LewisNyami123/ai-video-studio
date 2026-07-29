
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name= os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure = True
)

def upload_video(file_path: str, public_id: str = None, folder: str = "ai-videos"):
    try:
        result = cloudinary.uploader.upload(
            file_path,
            resource_type="video",
            folder=folder,
            public_id=public_id,
            overwrite=True,
        )
        return {
            "success": True,
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "duration": result.get("duration", 0),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        } 
       
def generate_thumbnail(public_id: str, width: int = 320, height: int = 180):
    url = cloudinary.CloudinaryImage(public_id).build_url(
        transformation=[
            {"width": width, "height": height, "crop": "fill"},
            {"format": "jpg"}
        ],
        resource_type="video"
    )
    return url