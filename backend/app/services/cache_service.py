"""
Redis caching service.

Key conventions:
  folders:all          → serialised list of all folder summaries
  folders:<id>         → single folder record
  images:folder:<fid>  → list of image summaries for a folder
  images:<id>          → single image detail (no prompt)
"""

import json
import logging
from typing import Optional, Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
    return _redis_client


def _safe(fn, *args, default=None, **kwargs):
    """Execute a Redis call; swallow errors and return default instead of crashing."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("Redis error: %s", exc)
        return default


# ─── Low-level get / set / delete ─────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    raw = _safe(_client().get, key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def cache_set(key: str, value: Any, ttl: int) -> None:
    _safe(_client().setex, key, ttl, json.dumps(value, default=str))


def cache_delete(key: str) -> None:
    _safe(_client().delete, key)


def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern (use sparingly)."""
    try:
        keys = _client().keys(pattern)
        if keys:
            _client().delete(*keys)
    except Exception as exc:
        logger.warning("Redis pattern-delete error: %s", exc)


# ─── Named helpers ─────────────────────────────────────────────────────────────

def get_folders_cache() -> Optional[Any]:
    return cache_get("folders:all")


def set_folders_cache(value: Any) -> None:
    settings = get_settings()
    cache_set("folders:all", value, settings.CACHE_TTL_FOLDERS)


def invalidate_folders_cache() -> None:
    cache_delete("folders:all")


def get_folder_cache(folder_id: str) -> Optional[Any]:
    return cache_get(f"folders:{folder_id}")


def set_folder_cache(folder_id: str, value: Any) -> None:
    settings = get_settings()
    cache_set(f"folders:{folder_id}", value, settings.CACHE_TTL_FOLDERS)


def invalidate_folder_cache(folder_id: str) -> None:
    cache_delete(f"folders:{folder_id}")


def get_images_for_folder_cache(folder_id: str) -> Optional[Any]:
    return cache_get(f"images:folder:{folder_id}")


def set_images_for_folder_cache(folder_id: str, value: Any) -> None:
    settings = get_settings()
    cache_set(f"images:folder:{folder_id}", value, settings.CACHE_TTL_IMAGES)


def invalidate_images_for_folder_cache(folder_id: str) -> None:
    cache_delete(f"images:folder:{folder_id}")


def get_image_detail_cache(image_id: str) -> Optional[Any]:
    return cache_get(f"images:{image_id}")


def set_image_detail_cache(image_id: str, value: Any) -> None:
    settings = get_settings()
    cache_set(f"images:{image_id}", value, settings.CACHE_TTL_IMAGE_DETAIL)


def invalidate_image_detail_cache(image_id: str) -> None:
    cache_delete(f"images:{image_id}")