"""
Gallery API
===========
GET /gallery  → paginated list of completed generations
"""

from fastapi import APIRouter

from app.core.db import get_gallery

router = APIRouter(tags=["Gallery"])


@router.get("/gallery")
async def gallery(page: int = 1, limit: int = 20):
    """
    Paginated gallery of completed AI-generated images.

    Each item contains:
    - image_url      : preferred display URL (Cloudinary or local fallback)
    - original_url   : user upload URL
    - cloudinary_url : Cloudinary URL (null if not uploaded)
    - uploaded       : bool
    - status         : "completed"
    - created_at

    Prompt text is NEVER included in gallery responses.
    """
    limit = min(limit, 100)
    return get_gallery(page=page, limit=limit)