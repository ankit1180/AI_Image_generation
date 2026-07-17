"""
Image routes.

SECURITY NOTE:
  - GET /images/{id}/prompt is the ONLY endpoint that returns a prompt.
  - It requires the X-Prompt-Secret header (verified by core.security.verify_prompt_secret).
  - All other endpoints call image_svc functions that strip the prompt field.
"""

import os
import uuid
import shutil
from typing import List

from fastapi import (
    APIRouter, HTTPException, status, Depends,
    UploadFile, File, Form, BackgroundTasks,
)

from app.core.models import (
    ImageSummary, ImageDetail, PromptResponse,
    UploadRequest, TaskResponse,
)
from app.core.exceptions import NotFoundError, AppError
from app.core.security import verify_prompt_secret
import app.services.image_service as image_svc
import app.services.folder_service as folder_svc
from app.queue.tasks import upload_image_task, upload_from_url_task

router = APIRouter(prefix="/images", tags=["Images"])

UPLOAD_TMP_DIR = "/tmp/ai_img_uploads"
os.makedirs(UPLOAD_TMP_DIR, exist_ok=True)


# ─── List images in a folder ───────────────────────────────────────────────────

@router.get(
    "/folder/{folder_id}",
    response_model=List[ImageSummary],
    summary="List images in a folder (no prompts)",
)
async def list_images(folder_id: str):
    """Returns image summaries for a folder. Prompt field is never present."""
    try:
        # Validate folder exists
        folder_svc.get_folder(folder_id)
        return image_svc.list_images_for_folder(folder_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── Get single image detail ───────────────────────────────────────────────────

@router.get(
    "/{image_id}",
    response_model=ImageDetail,
    summary="Get image detail (no prompt)",
)
async def get_image(image_id: str):
    """Returns full image detail. Prompt is NOT included."""
    try:
        return image_svc.get_image_detail(image_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── SECURE prompt endpoint ────────────────────────────────────────────────────

@router.get(
    "/{image_id}/prompt",
    response_model=PromptResponse,
    summary="[SECURE] Fetch image prompt",
    description=(
        "Returns the AI prompt for a given image. "
        "Requires **X-Prompt-Secret** header. "
        "This endpoint is intentionally separate and auth-gated."
    ),
)
async def get_prompt(
    image_id: str,
    _: str = Depends(verify_prompt_secret),   # auth gate
):
    try:
        return image_svc.get_image_prompt(image_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── Upload via multipart file (async) ────────────────────────────────────────

@router.post(
    "/upload/file",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload image file (async via Celery)",
)
async def upload_file(
    folder_id: str = Form(...),
    filename: str = Form(...),
    prompt: str = Form(...),
    metadata: str = Form("{}"),
    file: UploadFile = File(...),
):
    """
    Accepts a multipart upload. Saves file to tmp, creates a pending
    image record, and enqueues a Celery upload task.
    """
    import json as _json

    try:
        meta = _json.loads(metadata)
    except Exception:
        meta = {}

    try:
        folder_svc.get_folder(folder_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)

    # Save uploaded file to tmp
    tmp_path = os.path.join(UPLOAD_TMP_DIR, f"{uuid.uuid4()}_{file.filename}")
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create pending record
    req = UploadRequest(folder_id=folder_id, filename=filename, prompt=prompt, metadata=meta)
    record = image_svc.create_image_record(req)
    image_id = record["id"]

    # Enqueue async task
    task = upload_image_task.delay(
        image_id=image_id,
        file_path=tmp_path,
        folder_id=folder_id,
        cloudinary_folder=folder_id,
    )

    return TaskResponse(
        task_id=task.id,
        image_id=image_id,
        status="queued",
        message="Upload queued. Poll /tasks/{task_id} for status.",
    )


# ─── Upload via URL (async) ────────────────────────────────────────────────────

@router.post(
    "/upload/url",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload image from URL (async via Celery)",
)
async def upload_from_url(req: UploadRequest, image_url: str):
    """
    Accepts an image URL. Creates pending record and enqueues
    URL-fetch upload task.
    """
    try:
        folder_svc.get_folder(req.folder_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)

    record = image_svc.create_image_record(req)
    image_id = record["id"]

    task = upload_from_url_task.delay(
        image_id=image_id,
        image_url=image_url,
        folder_id=req.folder_id,
        cloudinary_folder=req.folder_id,
    )

    return TaskResponse(
        task_id=task.id,
        image_id=image_id,
        status="queued",
        message="URL upload queued. Poll /tasks/{task_id} for status.",
    )


# ─── Delete image ──────────────────────────────────────────────────────────────

@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an image record",
)
async def delete_image(image_id: str):
    try:
        image_svc.delete_image(image_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)