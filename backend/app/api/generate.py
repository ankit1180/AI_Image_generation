"""
Generation API
==============
POST /generate/similar       → submit a "Generate Similar Image" job
POST /generate/same          → submit a "Generate Same Image" job
                                (keep same background/outfit/pose, swap face)
GET  /generation/{task_id}   → poll task status (shared by both modes)

Security:
  - Frontend sends ONLY prompt_id (never prompt text)
  - Backend loads the hidden prompt from img_prompt.json internally
  - No prompt text is ever returned in any response

Structure:
  The two modes are deliberately separate endpoints, each with its own
  request/validation flow and its own Celery task dispatch
  (process_generation_similar / process_generation_same). They share only
  the low-level upload-handling helper (_save_upload) and the shared
  status-polling endpoint — there is no single combined "mode" branch.
"""

from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.core.db import create_task, get_task
from app.queue.tasks import process_generation_same, process_generation_similar
from app.services.prompt_loader import prompt_loader

router = APIRouter(tags=["Generation"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


# ---------------------------------------------------------------------------
# Shared helpers (validation / upload handling only — no generation logic)
# ---------------------------------------------------------------------------


def _validate_prompt_id(prompt_id: str) -> None:
    if not prompt_loader.prompt_exists(prompt_id):
        raise HTTPException(
            status_code=404,
            detail=f"prompt_id '{prompt_id}' not found",
        )


async def _save_upload(user_image: UploadFile) -> tuple[Path, int]:
    """Validate + persist the uploaded photo to disk. Returns (path, size)."""
    if not user_image.filename:
        raise HTTPException(status_code=400, detail="Invalid image file")

    ext = Path(user_image.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    filename = f"{uuid4().hex}{ext}"
    upload_path = settings.UPLOAD_DIR / filename
    total_size = 0

    try:
        async with aiofiles.open(upload_path, "wb") as fh:
            while chunk := await user_image.read(settings.UPLOAD_CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > settings.MAX_IMAGE_SIZE:
                    await fh.close()
                    upload_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=400,
                        detail="Image exceeds maximum allowed size (10 MB)",
                    )
                await fh.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save uploaded image") from exc

    if total_size == 0:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    return upload_path, total_size


# ---------------------------------------------------------------------------
# POST /generate/similar
# ---------------------------------------------------------------------------


@router.post("/generate/similar")
async def generate_similar(
    prompt_id: str = Form(..., description="ID of the selected preview image prompt"),
    user_image: UploadFile = File(..., description="User photo to transform"),
):
    """
    Submit a "Generate Similar Image" job — the default pipeline. The
    user's own photo is restyled toward the prompt; pose/background come
    from the user's upload.

    Input:
      - prompt_id  : ID from GET /folders/{folder_id} (no prompt text needed)
      - user_image : the user's uploaded photo

    Returns:
      - task_id : use with GET /generation/{task_id} to poll status

    The hidden prompt is loaded server-side from img_prompt.json.
    Prompt text is NEVER included in this response.
    """
    _validate_prompt_id(prompt_id)
    upload_path, total_size = await _save_upload(user_image)

    task_id = uuid4().hex
    try:
        create_task(
            task_id=task_id,
            prompt_id=prompt_id,
            upload_path=str(upload_path),
            filename=user_image.filename,
            size_bytes=total_size,
            mode="similar",
        )

        process_generation_similar.apply_async(
            args=[str(upload_path), prompt_id],
            task_id=task_id,
        )
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "task_id": task_id,
        "prompt_id": prompt_id,   # ID only – no text
        "mode": "similar",
        "status": "queued",
        "message": "Generation queued. Poll /generation/{task_id} for updates.",
    }


# ---------------------------------------------------------------------------
# POST /generate/same
# ---------------------------------------------------------------------------


@router.post("/generate/same")
async def generate_same(
    prompt_id: str = Form(..., description="ID of the selected preview image prompt"),
    user_image: UploadFile = File(..., description="User photo to transform"),
):
    """
    Submit a "Generate Same Image" job — keeps the style's sample image
    almost exactly (background, outfit, pose) and only swaps in the
    uploaded photo's face.

    Input:
      - prompt_id  : ID from GET /folders/{folder_id} (no prompt text needed)
      - user_image : the user's uploaded photo

    Returns:
      - task_id : use with GET /generation/{task_id} to poll status

    The hidden prompt is loaded server-side from img_prompt.json.
    Prompt text is NEVER included in this response.
    """
    _validate_prompt_id(prompt_id)
    upload_path, total_size = await _save_upload(user_image)

    task_id = uuid4().hex
    try:
        create_task(
            task_id=task_id,
            prompt_id=prompt_id,
            upload_path=str(upload_path),
            filename=user_image.filename,
            size_bytes=total_size,
            mode="same",
        )

        process_generation_same.apply_async(
            args=[str(upload_path), prompt_id],
            task_id=task_id,
        )
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "task_id": task_id,
        "prompt_id": prompt_id,   # ID only – no text
        "mode": "same",
        "status": "queued",
        "message": "Generation queued. Poll /generation/{task_id} for updates.",
    }


# ---------------------------------------------------------------------------
# GET /generation/{task_id}
# ---------------------------------------------------------------------------


@router.get("/generation/{task_id}")
async def get_generation_status(task_id: str):
    """
    Poll the status of a generation job.

    Returns:
      - task_id
      - status      : queued | processing | completed | failed
      - progress    : 0–100
      - image_url   : Cloudinary URL (preferred) or local fallback when complete
      - original_url: user's uploaded image URL (if uploaded to Cloudinary)
      - cloudinary_url: explicitly the Cloudinary URL (null until complete)
      - uploaded    : bool
      - error       : error message (only when status=failed)

    Never returns prompt text.
    """
    task = get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # Remove any internal fields before returning
    _INTERNAL_FIELDS = {"upload_path", "filename", "size_bytes", "_id"}
    safe_task = {k: v for k, v in task.items() if k not in _INTERNAL_FIELDS}

    return safe_task