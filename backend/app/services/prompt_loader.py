"""
Prompt Loader Service
=====================
Source of truth: img_prompt.json

Data model (internal only, NEVER sent to clients):
  [
    {
      "folder_name": "...",
      "images": [
        { "image_url": "...", "prompt": "..." },
        ...
      ]
    },
    ...
  ]

Public surface (safe to expose):
  - folder list (id, title, preview images)
  - prompt existence check
  - prompt text retrieval (internal use only)

Prompt text must NEVER leave this module toward any API response.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.core.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    """Turn a human-readable folder name into a stable, URL-safe id."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _folder_id(folder_name: str) -> str:
    """Deterministic id: slug + short hash for collision resistance."""
    slug = _slug(folder_name)
    h = hashlib.sha1(folder_name.encode()).hexdigest()[:6]
    return f"{slug}-{h}"


def _prompt_id(folder_id: str, index: int) -> str:
    return f"{folder_id}::p{index}"


# Keywords that signal "this folder rebuilds the whole scene" (background,
# outfit, lighting all change dramatically) rather than "subtle style filter
# on an otherwise-unchanged portrait". Scene-rebuild prompts need much more
# img2img strength to have any visible effect; portrait-style prompts need
# less so the face/composition stays intact. This is a heuristic, not a
# guarantee — override per-image via a "strength" key in img_prompt.json
# if a specific prompt needs tuning.
_SCENE_KEYWORDS = (
    "ipl", "cricket", "cyberpunk", "poster", "action", "sports",
    "futuristic", "superhero", "stadium",
)


def _infer_strength(folder_name: str) -> float:
    name = folder_name.lower()
    if any(kw in name for kw in _SCENE_KEYWORDS):
        return settings.SCENE_STRENGTH
    return settings.DEFAULT_STRENGTH


# ---------------------------------------------------------------------------
# Internal data classes
# ---------------------------------------------------------------------------


class _PromptEntry:
    """A single prompt entry (internal)."""

    __slots__ = ("prompt_id", "folder_id", "index", "image_url",
                 "cloudinary_url", "original_url", "public_id",
                 "uploaded", "_prompt", "strength_override", "guidance_override")

    def __init__(
        self,
        prompt_id: str,
        folder_id: str,
        index: int,
        image_url: str,
        prompt: str,
        strength_override: float | None = None,
        guidance_override: float | None = None,
    ) -> None:
        self.prompt_id = prompt_id
        self.folder_id = folder_id
        self.index = index
        # Cloudinary extension fields
        self.original_url: str = image_url
        self.cloudinary_url: str | None = None
        self.public_id: str | None = None
        self.uploaded: bool = False
        # The secret – never returned in API responses
        self._prompt: str = prompt
        # Optional per-image overrides (from img_prompt.json "strength" /
        # "guidance_scale" keys). None means "use the folder-level default".
        self.strength_override = strength_override
        self.guidance_override = guidance_override

    @property
    def display_image_url(self) -> str:
        """Frontend-safe URL: prefer Cloudinary, fall back to original."""
        return self.cloudinary_url or self.original_url

    def to_public_dict(self) -> dict[str, Any]:
        """Safe representation for the frontend (no prompt text)."""
        return {
            "prompt_id": self.prompt_id,
            "index": self.index,
            "original_url": self.original_url,
            "cloudinary_url": self.cloudinary_url,
            "public_id": self.public_id,
            "uploaded": self.uploaded,
            "image_url": self.display_image_url,  # convenience alias
        }

    def apply_cloudinary(
        self,
        cloudinary_url: str,
        public_id: str,
    ) -> None:
        self.cloudinary_url = cloudinary_url
        self.public_id = public_id
        self.uploaded = True


class _Folder:
    """A folder containing ordered prompt entries (internal)."""

    __slots__ = ("folder_id", "folder_name", "prompts", "default_strength")

    def __init__(self, folder_id: str, folder_name: str) -> None:
        self.folder_id = folder_id
        self.folder_name = folder_name
        self.prompts: list[_PromptEntry] = []
        self.default_strength: float = _infer_strength(folder_name)

    def to_public_dict(
        self,
        include_preview: bool = True,
        preview_limit: int = 4,
    ) -> dict[str, Any]:
        """
        Safe representation for GET /folders.
        Does NOT include prompt text anywhere.
        """
        preview_images = []
        if include_preview:
            preview_images = [
                p.to_public_dict()
                for p in self.prompts[:preview_limit]
            ]

        cover = self.prompts[0].display_image_url if self.prompts else None

        return {
            "folder_id": self.folder_id,
            "title": self.folder_name,
            "cover_image": cover,
            "prompt_count": len(self.prompts),
            "preview_images": preview_images,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        """
        Safe representation for GET /folders/{folder_id}.
        Returns all preview images – still no prompt text.
        """
        return {
            "folder_id": self.folder_id,
            "title": self.folder_name,
            "cover_image": self.prompts[0].display_image_url if self.prompts else None,
            "prompt_count": len(self.prompts),
            "images": [p.to_public_dict() for p in self.prompts],
        }


# ---------------------------------------------------------------------------
# PromptLoader singleton
# ---------------------------------------------------------------------------


class PromptLoader:
    """
    Loads img_prompt.json and provides safe, prompt-text-free access
    for the API layer, while exposing the hidden prompt text only
    internally for the generation pipeline.
    """

    def __init__(self) -> None:
        self._folders: dict[str, _Folder] = {}       # keyed by folder_id
        self._prompts: dict[str, _PromptEntry] = {}  # keyed by prompt_id
        self.reload()

    # -----------------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------------

    def reload(self) -> None:
        """(Re)load data from img_prompt.json."""
        self._folders = {}
        self._prompts = {}
        self._load_from_file()

    def _load_from_file(self) -> None:
        json_path: Path = settings.IMG_PROMPT_FILE

        if not json_path.exists():
            print(f"[PromptLoader] WARNING: {json_path} not found – no folders loaded.")
            return

        try:
            raw = json_path.read_text(encoding="utf-8")
            # The file uses Windows CRLF and a non-standard outer wrapper
            raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip()

            # The file wraps folder objects with { {…}, {…} } instead of [{…},{…}]
            # We normalise it to a JSON array.
            if raw.startswith("{") and not raw.startswith('{"'):
                raw = "[" + raw.lstrip("{").rstrip("}") + "]"

            folders_raw: list[dict] = json.loads(raw)
        except Exception as exc:
            print(f"[PromptLoader] ERROR reading {json_path}: {exc}")
            return

        for folder_raw in folders_raw:
            folder_name: str = folder_raw.get("folder_name", "Unnamed Folder")
            images: list[dict] = folder_raw.get("images", [])

            fid = _folder_id(folder_name)
            folder = _Folder(folder_id=fid, folder_name=folder_name)

            for idx, img in enumerate(images):
                image_url = img.get("image_url", "")
                prompt_text = img.get("prompt", "")
                # Optional manual overrides — most prompts won't set these
                # and will fall back to the folder's inferred default.
                strength_override = img.get("strength")
                guidance_override = img.get("guidance_scale")

                pid = _prompt_id(fid, idx)
                entry = _PromptEntry(
                    prompt_id=pid,
                    folder_id=fid,
                    index=idx,
                    image_url=image_url,
                    prompt=prompt_text,
                    strength_override=strength_override,
                    guidance_override=guidance_override,
                )
                folder.prompts.append(entry)
                self._prompts[pid] = entry

            self._folders[fid] = folder

        print(
            f"[PromptLoader] Loaded {len(self._folders)} folders, "
            f"{len(self._prompts)} prompts."
        )

    # -----------------------------------------------------------------------
    # Public API – folder/image info (NO prompt text)
    # -----------------------------------------------------------------------

    def list_folders(self) -> list[dict[str, Any]]:
        """Return public folder list – safe for frontend."""
        return [
            f.to_public_dict(include_preview=True, preview_limit=4)
            for f in self._folders.values()
        ]

    def get_folder(self, folder_id: str) -> dict[str, Any] | None:
        """Return public folder detail with all preview images."""
        folder = self._folders.get(folder_id)
        return folder.to_detail_dict() if folder else None

    def folder_exists(self, folder_id: str) -> bool:
        return folder_id in self._folders

    def prompt_exists(self, prompt_id: str) -> bool:
        return prompt_id in self._prompts

    def get_preview_image(self, prompt_id: str) -> dict[str, Any] | None:
        """Return public image info (no prompt text)."""
        entry = self._prompts.get(prompt_id)
        return entry.to_public_dict() if entry else None

    # -----------------------------------------------------------------------
    # Internal API – generation pipeline only, NEVER return to clients
    # -----------------------------------------------------------------------

    def get_prompt_text(self, prompt_id: str) -> str:
        """
        INTERNAL USE ONLY.
        Returns the hidden prompt text for the AI generation pipeline.
        This must NEVER be included in any API response.
        """
        entry = self._prompts.get(prompt_id)
        if entry is None:
            raise ValueError(f"Prompt not found: {prompt_id!r}")
        return entry._prompt

    def get_generation_config(self, prompt_id: str) -> dict[str, Any]:
        """
        INTERNAL USE ONLY.
        Full config dict for generator.generate().
        Contains prompt text – must NEVER be returned to clients.
        """
        entry = self._prompts.get(prompt_id)
        if entry is None:
            raise ValueError(f"Prompt not found: {prompt_id!r}")
        folder = self._folders.get(entry.folder_id)
        strength = (
            entry.strength_override
            if entry.strength_override is not None
            else (folder.default_strength if folder else settings.DEFAULT_STRENGTH)
        )
        guidance = (
            entry.guidance_override
            if entry.guidance_override is not None
            else settings.DEFAULT_GUIDANCE_SCALE
        )
        return {
            "prompt": entry._prompt,
            "negative_prompt": settings.DEFAULT_NEGATIVE_PROMPT,
            "strength": strength,
            "guidance_scale": guidance,
            "lcm_steps": settings.LCM_STEPS,
            "lcm_guidance_scale": settings.LCM_GUIDANCE_SCALE,
            # The folder's own preview/sample image — used as the img2img
            # BASE (pose/background/composition) instead of the user's
            # upload, when USE_SAMPLE_AS_BASE is enabled. Prefer the
            # Cloudinary-mirrored copy if we have one (faster, more
            # reliable than re-fetching the original promptwale.com URL
            # every time).
            "sample_image_url": entry.cloudinary_url or entry.original_url,
        }

    # -----------------------------------------------------------------------
    # Cloudinary integration – extend images without replacing URLs
    # -----------------------------------------------------------------------

    def apply_cloudinary_url(
        self,
        prompt_id: str,
        cloudinary_url: str,
        public_id: str,
    ) -> None:
        """
        Extend an image entry with Cloudinary info.
        The original_url is preserved; cloudinary_url is added alongside it.
        """
        entry = self._prompts.get(prompt_id)
        if entry:
            entry.apply_cloudinary(cloudinary_url, public_id)


# Singleton
prompt_loader = PromptLoader()