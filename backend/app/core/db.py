"""
Database Layer
==============
MongoDB collections:
  - tasks     : generation task tracking
  - images    : completed generation results (saved for gallery)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient

from app.core.config import settings

client = MongoClient(settings.MONGO_URI)
db = client[settings.DB_NAME]

# Collections
tasks_collection = db["tasks"]
images_collection = db["images"]


def ensure_indexes() -> None:
    """Create indexes on startup."""
    tasks_collection.create_index([("task_id", ASCENDING)], unique=True)
    tasks_collection.create_index([("status", ASCENDING), ("created_at", DESCENDING)])

    images_collection.create_index([("created_at", DESCENDING)])
    images_collection.create_index([("prompt_id", ASCENDING)])
    images_collection.create_index([("status", ASCENDING), ("created_at", DESCENDING)])


# ---------------------------------------------------------------------------
# Task management
# ---------------------------------------------------------------------------


def create_task(
    task_id: str,
    prompt_id: str,
    upload_path: str,
    filename: str,
    size_bytes: int,
    mode: str = "similar",
) -> None:
    """Create a new generation task record.

    mode : "similar" (default pipeline) or "same" (face-swap-only /
           keep-same-background pipeline). Kept as an explicit field on the
           task record so GET /generation/{task_id} can report which mode
           produced the result.
    """
    now = datetime.now(UTC)
    tasks_collection.insert_one({
        "task_id": task_id,
        "prompt_id": prompt_id,          # the only ID – no prompt text stored here
        "upload_path": upload_path,
        "filename": filename,
        "size_bytes": size_bytes,
        "mode": mode,
        "status": "queued",
        "progress": 10,
        "image_url": None,
        "cloudinary_url": None,
        "public_id": None,
        "uploaded": False,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
    })


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    image_url: str | None = None,
    cloudinary_url: str | None = None,
    public_id: str | None = None,
    uploaded: bool | None = None,
    error: str | None = None,
) -> None:
    """Partially update a generation task."""
    now = datetime.now(UTC)
    updates: dict[str, Any] = {"updated_at": now}

    if status is not None:
        updates["status"] = status
        if status == "processing":
            updates["started_at"] = now
        elif status == "completed":
            updates["completed_at"] = now
            updates["progress"] = 100
        elif status == "failed":
            updates["failed_at"] = now

    if progress is not None:
        updates["progress"] = max(0, min(progress, 100))
    if image_url is not None:
        updates["image_url"] = image_url
    if cloudinary_url is not None:
        updates["cloudinary_url"] = cloudinary_url
    if public_id is not None:
        updates["public_id"] = public_id
    if uploaded is not None:
        updates["uploaded"] = uploaded
    if error is not None:
        updates["error"] = error

    tasks_collection.update_one({"task_id": task_id}, {"$set": updates})


def get_task(task_id: str) -> dict[str, Any] | None:
    """Retrieve a task record (excludes MongoDB _id)."""
    return tasks_collection.find_one({"task_id": task_id}, {"_id": 0})


# ---------------------------------------------------------------------------
# Gallery image persistence
# ---------------------------------------------------------------------------


def save_generated_image(
    task_id: str,
    prompt_id: str,
    original_url: str,
    cloudinary_url: str | None,
    public_id: str | None,
    uploaded: bool,
) -> str:
    """
    Persist a completed generation result for the gallery.
    Stores Cloudinary info alongside the original URL – never the prompt text.
    """
    now = datetime.now(UTC)
    result = images_collection.insert_one({
        "task_id": task_id,
        "prompt_id": prompt_id,          # only the ID, not the text
        "original_url": original_url,
        "cloudinary_url": cloudinary_url,
        "public_id": public_id,
        "uploaded": uploaded,
        # Frontend-preferred URL (Cloudinary if available, else original)
        "image_url": cloudinary_url or original_url,
        "status": "completed",
        "created_at": now,
        "updated_at": now,
    })
    return str(result.inserted_id)


def get_gallery(page: int = 1, limit: int = 20) -> dict[str, Any]:
    """Paginated gallery of completed generations."""
    skip = (page - 1) * limit
    items = list(
        images_collection.find(
            {"status": "completed"},
            {"_id": 0, "prompt_id": 0},  # exclude prompt_id from public responses
        )
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    total = images_collection.count_documents({"status": "completed"})
    return {"page": page, "limit": limit, "total": total, "items": items}