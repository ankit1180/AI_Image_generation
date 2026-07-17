"""
Folder service — orchestrates DB + cache for all folder operations.
"""

from typing import List, Dict, Any
from datetime import datetime
import uuid

from app.core.models import FolderRecord, FolderSummary, CreateFolderRequest
from app.core.exceptions import NotFoundError
import app.core.json_db as json_db
import app.services.cache_service as cache


def _count_images_for_folder(folder_id: str) -> int:
    try:
        imgs = json_db.get_images_for_folder(folder_id)
        return len(imgs)
    except Exception:
        return 0


def _to_summary(folder: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": folder["id"],
        "name": folder["name"],
        "description": folder.get("description", ""),
        "created_at": folder["created_at"],
        "image_count": _count_images_for_folder(folder["id"]),
    }


# ─── Public API ────────────────────────────────────────────────────────────────

def list_folders() -> List[Dict[str, Any]]:
    """Return all folders as summaries. Cached."""
    cached = cache.get_folders_cache()
    if cached is not None:
        return cached

    folders = json_db.get_all_folders()
    summaries = [_to_summary(f) for f in folders.values()]
    summaries.sort(key=lambda x: x["created_at"], reverse=True)
    cache.set_folders_cache(summaries)
    return summaries


def get_folder(folder_id: str) -> Dict[str, Any]:
    """Return a single folder summary. Cached."""
    cached = cache.get_folder_cache(folder_id)
    if cached is not None:
        return cached

    folder = json_db.get_folder(folder_id)  # raises NotFoundError
    summary = _to_summary(folder)
    cache.set_folder_cache(folder_id, summary)
    return summary


def create_folder(req: CreateFolderRequest) -> Dict[str, Any]:
    """Create a new folder, invalidate list cache."""
    record = FolderRecord(
        id=str(uuid.uuid4()),
        name=req.name.strip(),
        description=req.description.strip(),
        created_at=datetime.utcnow().isoformat(),
    )
    json_db.create_folder(record.model_dump())
    cache.invalidate_folders_cache()
    return _to_summary(record.model_dump())


def delete_folder(folder_id: str) -> None:
    """Delete folder + cascade images, invalidate caches."""
    json_db.delete_folder(folder_id)  # raises NotFoundError if missing
    cache.invalidate_folders_cache()
    cache.invalidate_folder_cache(folder_id)
    cache.invalidate_images_for_folder_cache(folder_id)