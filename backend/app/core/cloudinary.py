"""
Cloudinary Integration
=======================
All uploads return a full result dict containing:
  - secure_url
  - public_id

Images are EXTENDED, never replaced:
  original_url   → kept as-is (source of truth)
  cloudinary_url → new Cloudinary secure_url
  public_id      → Cloudinary asset identifier
  uploaded       → True after successful upload
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cloudinary
import cloudinary.uploader

from app.core.config import settings


def _is_configured() -> bool:
    """Return True if all required Cloudinary env vars are present."""
    return bool(
        settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_CLOUD_NAME not in ("", "xxx", "your_cloud_name")
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_KEY not in ("", "xxx")
        and settings.CLOUDINARY_API_SECRET
        and settings.CLOUDINARY_API_SECRET not in ("", "xxx")
    )


def _configure() -> bool:
    """Configure cloudinary SDK. Returns True if configuration succeeded."""
    if not _is_configured():
        return False
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    return True


def _base_options(
    *,
    public_id: str | None = None,
    context: dict[str, str] | None = None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "resource_type": "image",
        "folder": settings.CLOUDINARY_FOLDER,
        "overwrite": False,
        "use_filename": True,
        "unique_filename": True,
    }
    if public_id:
        opts["public_id"] = public_id
    if context:
        opts["context"] = context
    return opts


class CloudinaryResult:
    """Parsed upload result – always has both URLs."""

    def __init__(
        self,
        original_url: str,
        cloudinary_url: str,
        public_id: str,
        uploaded: bool,
    ) -> None:
        self.original_url = original_url
        self.cloudinary_url = cloudinary_url
        self.public_id = public_id
        self.uploaded = uploaded

    @property
    def display_url(self) -> str:
        """Prefer Cloudinary, fallback to original."""
        return self.cloudinary_url if self.uploaded else self.original_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_url": self.original_url,
            "cloudinary_url": self.cloudinary_url if self.uploaded else None,
            "public_id": self.public_id if self.uploaded else None,
            "uploaded": self.uploaded,
        }


def upload_file(
    file_path: str | Path,
    original_url: str = "",
    *,
    public_id: str | None = None,
    context: dict[str, str] | None = None,
) -> CloudinaryResult:
    """
    Upload a local file to Cloudinary.
    Returns a CloudinaryResult; on failure, marks uploaded=False and
    uses original_url as the fallback.
    """
    if not _configure():
        return CloudinaryResult(
            original_url=original_url or str(file_path),
            cloudinary_url="",
            public_id="",
            uploaded=False,
        )

    try:
        result = cloudinary.uploader.upload(
            str(file_path),
            **_base_options(public_id=public_id, context=context),
        )
        return CloudinaryResult(
            original_url=original_url or str(file_path),
            cloudinary_url=result["secure_url"],
            public_id=result["public_id"],
            uploaded=True,
        )
    except Exception as exc:
        print(f"[Cloudinary] Upload failed for {file_path}: {exc}")
        return CloudinaryResult(
            original_url=original_url or str(file_path),
            cloudinary_url="",
            public_id="",
            uploaded=False,
        )


def upload_stream(
    file_stream,
    original_url: str = "",
    *,
    public_id: str | None = None,
    context: dict[str, str] | None = None,
) -> CloudinaryResult:
    """
    Upload a file-like stream to Cloudinary.
    Returns a CloudinaryResult; on failure, falls back to original_url.
    """
    if not _configure():
        return CloudinaryResult(
            original_url=original_url,
            cloudinary_url="",
            public_id="",
            uploaded=False,
        )

    try:
        result = cloudinary.uploader.upload(
            file_stream,
            **_base_options(public_id=public_id, context=context),
        )
        return CloudinaryResult(
            original_url=original_url,
            cloudinary_url=result["secure_url"],
            public_id=result["public_id"],
            uploaded=True,
        )
    except Exception as exc:
        print(f"[Cloudinary] Stream upload failed: {exc}")
        return CloudinaryResult(
            original_url=original_url,
            cloudinary_url="",
            public_id="",
            uploaded=False,
        )