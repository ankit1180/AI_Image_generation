"""
JSON-based database layer.

Schema:
{
  "folders": {
    "<folder_id>": { id, name, description, created_at }
  },
  "images": {
    "<image_id>": { id, folder_id, filename, cloudinary_url,
                    public_id, prompt, metadata, status, ... }
  }
}

Prompt field lives here but is NEVER returned by service-layer
methods that feed the listing/detail APIs.
"""

import json
import os
import threading
from typing import Dict, Optional, Any
from datetime import datetime

from app.core.config import get_settings
from app.core.exceptions import NotFoundError

_lock = threading.Lock()


def _db_path() -> str:
    return get_settings().DB_PATH


def _load() -> Dict[str, Any]:
    path = _db_path()
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    if not os.path.exists(path):
        return {"folders": {}, "images": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: Dict[str, Any]) -> None:
    path = _db_path()
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)   # atomic on POSIX


# ─── Folder operations ─────────────────────────────────────────────────────────

def get_all_folders() -> Dict[str, Any]:
    with _lock:
        return _load()["folders"]


def get_folder(folder_id: str) -> Dict[str, Any]:
    with _lock:
        data = _load()
        folder = data["folders"].get(folder_id)
        if not folder:
            raise NotFoundError("Folder", folder_id)
        return folder


def create_folder(folder: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        data = _load()
        data["folders"][folder["id"]] = folder
        _save(data)
        return folder


def delete_folder(folder_id: str) -> None:
    with _lock:
        data = _load()
        if folder_id not in data["folders"]:
            raise NotFoundError("Folder", folder_id)
        del data["folders"][folder_id]
        # cascade-delete images
        data["images"] = {
            k: v for k, v in data["images"].items()
            if v["folder_id"] != folder_id
        }
        _save(data)


# ─── Image operations ──────────────────────────────────────────────────────────

def get_images_for_folder(folder_id: str) -> Dict[str, Any]:
    """Returns ALL image fields including prompt (callers strip it)."""
    with _lock:
        data = _load()
        return {
            k: v for k, v in data["images"].items()
            if v["folder_id"] == folder_id
        }


def get_image(image_id: str) -> Dict[str, Any]:
    """Returns full image record including prompt."""
    with _lock:
        data = _load()
        img = data["images"].get(image_id)
        if not img:
            raise NotFoundError("Image", image_id)
        return img


def create_image(image: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        data = _load()
        data["images"][image["id"]] = image
        _save(data)
        return image


def update_image(image_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        data = _load()
        img = data["images"].get(image_id)
        if not img:
            raise NotFoundError("Image", image_id)
        img.update(fields)
        img["updated_at"] = datetime.utcnow().isoformat()
        data["images"][image_id] = img
        _save(data)
        return img


def delete_image(image_id: str) -> None:
    with _lock:
        data = _load()
        if image_id not in data["images"]:
            raise NotFoundError("Image", image_id)
        del data["images"][image_id]
        _save(data)