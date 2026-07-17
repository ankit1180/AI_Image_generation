"""
Folders API
============
GET  /folders              → list all folders with cover + 4 preview images
GET  /folders/{folder_id}  → full folder with all preview images

Security: prompt text is NEVER included in any response.
"""

from fastapi import APIRouter, HTTPException

from app.services.prompt_loader import prompt_loader

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.get("")
async def list_folders():
    """
    All folders. Each contains folder_id, title, cover_image,
    prompt_count, and the first 4 preview_images.
    No prompt text anywhere.
    """
    folders = prompt_loader.list_folders()
    return {"total": len(folders), "items": folders}


@router.get("/{folder_id}")
async def get_folder(folder_id: str):
    """
    Single folder with ALL preview images.
    Each image has: prompt_id, image_url, original_url,
    cloudinary_url, public_id, uploaded.
    No prompt text anywhere.
    """
    folder = prompt_loader.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder