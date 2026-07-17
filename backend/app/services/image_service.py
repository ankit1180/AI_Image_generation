"""
Image service — all image read operations.

SECURITY RULE: _strip_prompt() is called on every path that feeds
a public API response. The raw record (with prompt) is only returned
by get_image_prompt(), which sits behind an auth dependency.
"""

from typing import List, Dict, Any
import uuid
from datetime import datetime

from app.core.models import ImageRecord, UploadRequest
from app.core.exceptions import NotFoundError
import app.core.json_db as json_db
import app.services.cache_service as cache


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _strip_prompt(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the record with the prompt field removed."""
    safe = dict(record)
    safe.pop("prompt", None)
    return safe


def _to_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal fields for folder image listings."""
    return {
        "id": record["id"],
        "filename": record["filename"],
        "cloudinary_url": record.get("cloudinary_url", ""),
        "public_id": record.get("public_id", ""),
        "status": record.get("status", "pending"),
        "metadata": record.get("metadata", {}),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


# ─── Public read API (no prompt) ───────────────────────────────────────────────

def list_images_for_folder(folder_id: str) -> List[Dict[str, Any]]:
    """Return image summaries for a folder — prompt is NEVER included."""
    cached = cache.get_images_for_folder_cache(folder_id)
    if cached is not None:
        return cached

    images = json_db.get_images_for_folder(folder_id)
    summaries = [_to_summary(img) for img in images.values()]
    summaries.sort(key=lambda x: x["created_at"], reverse=True)
    cache.set_images_for_folder_cache(folder_id, summaries)
    return summaries


def get_image_detail(image_id: str) -> Dict[str, Any]:
    """Return full image detail — prompt is NEVER included."""
    cached = cache.get_image_detail_cache(image_id)
    if cached is not None:
        return cached

    record = json_db.get_image(image_id)  # raises NotFoundError
    detail = _strip_prompt(record)
    cache.set_image_detail_cache(image_id, detail)
    return detail


# ─── Secure prompt fetch (auth-gated at route level) ──────────────────────────

def get_image_prompt(image_id: str) -> Dict[str, Any]:
    """Return ONLY the prompt for an image. Never cached."""
    record = json_db.get_image(image_id)  # raises NotFoundError
    return {
        "image_id": image_id,
        "prompt": record.get("prompt", ""),
    }


# ─── Write operations (called by workers + routes) ────────────────────────────

def create_image_record(req: UploadRequest) -> Dict[str, Any]:
    """
    Create a pending image record in the DB.
    Returns the full record (used internally by the upload task).
    """
    record = ImageRecord(
        id=str(uuid.uuid4()),
        folder_id=req.folder_id,
        filename=req.filename,
        prompt=req.prompt,          # stored in DB only
        metadata=req.metadata,
        status="pending",
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )
    json_db.create_image(record.model_dump())
    # Invalidate folder image list cache
    cache.invalidate_images_for_folder_cache(req.folder_id)
    cache.invalidate_folders_cache()  # image_count changed
    return record.model_dump()


def update_image_after_upload(
    image_id: str,
    cloudinary_url: str,
    public_id: str,
    extra_metadata: Dict[str, Any],
    folder_id: str,
) -> None:
    """Called by Celery worker after a successful Cloudinary upload."""
    json_db.update_image(image_id, {
        "cloudinary_url": cloudinary_url,
        "public_id": public_id,
        "status": "done",
        "metadata": extra_metadata,
    })
    cache.invalidate_image_detail_cache(image_id)
    cache.invalidate_images_for_folder_cache(folder_id)


def mark_image_error(image_id: str, folder_id: str, error: str) -> None:
    """Called by Celery worker on upload failure."""
    json_db.update_image(image_id, {"status": "error", "error": error})
    cache.invalidate_image_detail_cache(image_id)
    cache.invalidate_images_for_folder_cache(folder_id)


def delete_image(image_id: str) -> None:
    """Delete image record and invalidate caches."""
    record = json_db.get_image(image_id)
    folder_id = record["folder_id"]
    json_db.delete_image(image_id)
    cache.invalidate_image_detail_cache(image_id)
    cache.invalidate_images_for_folder_cache(folder_id)
    cache.invalidate_folders_cache()