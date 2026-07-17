"""
Cloudinary service layer.

All Cloudinary SDK calls are isolated here so the rest of the
application has zero SDK coupling.
"""

import logging
from typing import Dict, Any, Optional

import cloudinary
import cloudinary.uploader
import cloudinary.api

from core.config import get_settings
from core.exceptions import CloudinaryError

logger = logging.getLogger(__name__)

_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    cloudinary.config(
        cloud_name=s.CLOUDINARY_CLOUD_NAME,
        api_key=s.CLOUDINARY_API_KEY,
        api_secret=s.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configured = True


def upload_image(
    file_path: str,
    public_id: Optional[str] = None,
    folder: Optional[str] = None,
    extra_tags: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Upload a local file to Cloudinary.
    Returns dict with { cloudinary_url, public_id, width, height, format, bytes }.
    """
    _ensure_configured()
    try:
        options: Dict[str, Any] = {
            "resource_type": "image",
            "overwrite": True,
            "tags": extra_tags or [],
        }
        if public_id:
            options["public_id"] = public_id
        if folder:
            options["folder"] = folder

        result = cloudinary.uploader.upload(file_path, **options)
        logger.info("Cloudinary upload OK: %s", result.get("public_id"))
        return {
            "cloudinary_url": result.get("secure_url", ""),
            "public_id": result.get("public_id", ""),
            "width": result.get("width", 0),
            "height": result.get("height", 0),
            "format": result.get("format", ""),
            "bytes": result.get("bytes", 0),
            "version": result.get("version", ""),
        }
    except Exception as exc:
        logger.error("Cloudinary upload failed: %s", exc)
        raise CloudinaryError(str(exc))


def upload_from_url(
    image_url: str,
    public_id: Optional[str] = None,
    folder: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload from a remote URL (fetch mode)."""
    _ensure_configured()
    try:
        options: Dict[str, Any] = {
            "resource_type": "image",
            "type": "fetch",
            "overwrite": True,
        }
        if public_id:
            options["public_id"] = public_id
        if folder:
            options["folder"] = folder

        result = cloudinary.uploader.upload(image_url, **options)
        return {
            "cloudinary_url": result.get("secure_url", ""),
            "public_id": result.get("public_id", ""),
            "width": result.get("width", 0),
            "height": result.get("height", 0),
            "format": result.get("format", ""),
            "bytes": result.get("bytes", 0),
        }
    except Exception as exc:
        raise CloudinaryError(str(exc))


def delete_image(public_id: str) -> Dict[str, Any]:
    """Delete an asset from Cloudinary by public_id."""
    _ensure_configured()
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="image")
        logger.info("Cloudinary delete: %s → %s", public_id, result)
        return result
    except Exception as exc:
        raise CloudinaryError(str(exc))


def get_image_details(public_id: str) -> Dict[str, Any]:
    """Fetch resource metadata from Cloudinary."""
    _ensure_configured()
    try:
        return cloudinary.api.resource(public_id)
    except Exception as exc:
        raise CloudinaryError(str(exc))


def build_transformed_url(
    public_id: str,
    width: int = 800,
    height: Optional[int] = None,
    crop: str = "fill",
    quality: str = "auto",
    format: str = "auto",
) -> str:
    """Build a transformation URL without a network call."""
    _ensure_configured()
    transformations: Dict[str, Any] = {
        "width": width,
        "crop": crop,
        "quality": quality,
        "fetch_format": format,
    }
    if height:
        transformations["height"] = height

    return cloudinary.utils.cloudinary_url(public_id, **transformations)[0]