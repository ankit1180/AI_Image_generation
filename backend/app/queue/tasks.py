"""
Celery Tasks
=============
process_generation_similar / process_generation_same: core generation workers.

Flow:
  1. Mark processing
  2. Load HIDDEN prompt via prompt_loader (internal only, never exposed)
  3. Run AI generator (or mock)
  4. Upload generated image to Cloudinary via app.core.cloudinary
  5. Save to gallery (MongoDB images collection)
  6. Mark completed with result URL
"""

import logging
import os
from typing import Any, Dict, Optional

from celery.utils.log import get_task_logger

from app.queue.celery_app import celery_app
from app.services.generator import generator
from app.services.prompt_loader import prompt_loader
from app.core.db import update_task, save_generated_image

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# Shared finalize step — Cloudinary upload + gallery save + task completion.
# Identical bookkeeping for both modes, so it's factored out once here; the
# two tasks below stay focused purely on "which generator method to call".
# ---------------------------------------------------------------------------


def _finalize_generation(
    task_id: str,
    prompt_id: str,
    upload_path: str,
    local_output_url: str,
    mode: str,
) -> Dict[str, Any]:
    logger.info("Generation done: task=%s mode=%s output=%s", task_id, mode, local_output_url)
    update_task(task_id, progress=70, image_url=local_output_url)

    # ── Upload generated image to Cloudinary ────────────────────────────────
    cloudinary_url: Optional[str] = None
    public_id: Optional[str] = None
    uploaded = False

    try:
        from app.core.config import settings
        from app.core.cloudinary import upload_file as cloudinary_upload

        output_abs = str(settings.OUTPUT_DIR / os.path.basename(local_output_url))
        if os.path.exists(output_abs):
            result = cloudinary_upload(
                file_path=output_abs,
                original_url=local_output_url,
                context={
                    "task_id": task_id,
                    "prompt_id": prompt_id,
                    "source": "generated",
                    "mode": mode,
                },
            )
            if result.uploaded:
                cloudinary_url = result.cloudinary_url
                public_id = result.public_id
                uploaded = True
                logger.info("Cloudinary upload done: task=%s url=%s", task_id, cloudinary_url)
    except Exception as cloud_exc:
        logger.warning("Cloudinary upload skipped (task=%s): %s", task_id, cloud_exc)

    # ── Save to gallery ──────────────────────────────────────────────────────
    preferred_url = cloudinary_url or local_output_url
    save_generated_image(
        task_id=task_id,
        prompt_id=prompt_id,
        original_url=local_output_url,
        cloudinary_url=cloudinary_url,
        public_id=public_id,
        uploaded=uploaded,
    )

    # ── Mark completed ───────────────────────────────────────────────────────
    update_task(
        task_id,
        status="completed",
        progress=100,
        image_url=preferred_url,
        cloudinary_url=cloudinary_url,
        public_id=public_id,
        uploaded=uploaded,
    )

    # Clean up user upload
    if os.path.exists(upload_path):
        try:
            os.remove(upload_path)
        except OSError:
            pass

    logger.info("process_generation_%s finished: task=%s image=%s", mode, task_id, preferred_url)
    return {"task_id": task_id, "image_url": preferred_url, "status": "completed"}


# ---------------------------------------------------------------------------
# "Generate Similar Image" — the original, default pipeline. Base = the
# user's own uploaded photo, restyled toward the prompt.
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="app.queue.tasks.process_generation_similar",
    max_retries=3,
    default_retry_delay=15,
)
def process_generation_similar(
    self,
    upload_path: str,
    prompt_id: str,
) -> Dict[str, Any]:
    """
    "Generate Similar Image" pipeline.

    Parameters (safe to log):
      upload_path : local path of user-uploaded image
      prompt_id   : public-facing ID used to look up the hidden prompt

    Prompt text is loaded internally and NEVER returned or logged.
    """
    task_id: str = self.request.id
    logger.info("process_generation_similar started: task=%s prompt_id=%s", task_id, prompt_id)

    try:
        update_task(task_id, status="processing", progress=10)

        try:
            prompt_config = prompt_loader.get_generation_config(prompt_id)
        except ValueError as exc:
            raise RuntimeError(f"Invalid prompt_id: {exc}") from exc

        update_task(task_id, progress=20)

        local_output_url = generator.generate_similar(
            image_path=upload_path,
            prompt_config=prompt_config,
        )

        return _finalize_generation(
            task_id=task_id,
            prompt_id=prompt_id,
            upload_path=upload_path,
            local_output_url=local_output_url,
            mode="similar",
        )

    except Exception as exc:
        logger.error("process_generation_similar error (task=%s): %s", task_id, exc, exc_info=True)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            update_task(task_id, status="failed", error=str(exc))
            return {"task_id": task_id, "status": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# "Generate Same Image" — face-swap-only / "Keep Same Background". Base =
# the folder's sample image; only the face shifts toward the user's photo.
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="app.queue.tasks.process_generation_same",
    max_retries=3,
    default_retry_delay=15,
)
def process_generation_same(
    self,
    upload_path: str,
    prompt_id: str,
) -> Dict[str, Any]:
    """
    "Generate Same Image" pipeline (keeps the sample's background, outfit,
    and pose — only the face changes).

    Parameters (safe to log):
      upload_path : local path of user-uploaded image
      prompt_id   : public-facing ID used to look up the hidden prompt

    Prompt text is loaded internally and NEVER returned or logged.
    """
    task_id: str = self.request.id
    logger.info("process_generation_same started: task=%s prompt_id=%s", task_id, prompt_id)

    try:
        update_task(task_id, status="processing", progress=10)

        try:
            prompt_config = prompt_loader.get_generation_config(prompt_id)
        except ValueError as exc:
            raise RuntimeError(f"Invalid prompt_id: {exc}") from exc

        update_task(task_id, progress=20)

        local_output_url = generator.generate_same(
            image_path=upload_path,
            prompt_config=prompt_config,
        )

        return _finalize_generation(
            task_id=task_id,
            prompt_id=prompt_id,
            upload_path=upload_path,
            local_output_url=local_output_url,
            mode="same",
        )

    except Exception as exc:
        logger.error("process_generation_same error (task=%s): %s", task_id, exc, exc_info=True)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            update_task(task_id, status="failed", error=str(exc))
            return {"task_id": task_id, "status": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# Admin image upload tasks (used by app.api.images, currently disabled in
# main.py). These were previously referenced by images.py but never defined,
# which would have raised an ImportError the moment that router was enabled.
# They operate on the separate json_db-backed folder/image admin model
# (app.services.image_service), NOT on the Mongo-backed generation pipeline
# above — the two are intentionally different data models.
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.queue.tasks.upload_image_task", max_retries=3)
def upload_image_task(
    self,
    image_id: str,
    file_path: str,
    folder_id: str,
    cloudinary_folder: str,
) -> Dict[str, Any]:
    from app.core.cloudinary import upload_file as cloudinary_upload
    import app.services.image_service as image_svc

    try:
        result = cloudinary_upload(
            file_path=file_path,
            original_url=file_path,
            context={"image_id": image_id, "folder_id": folder_id},
        )
        if not result.uploaded:
            raise RuntimeError("Cloudinary upload failed")

        image_svc.update_image_after_upload(
            image_id=image_id,
            cloudinary_url=result.cloudinary_url,
            public_id=result.public_id,
            extra_metadata={},
            folder_id=folder_id,
        )
        return {"image_id": image_id, "status": "done", "cloudinary_url": result.cloudinary_url}
    except Exception as exc:
        logger.error("upload_image_task error (image=%s): %s", image_id, exc, exc_info=True)
        import app.services.image_service as image_svc
        image_svc.mark_image_error(image_id, folder_id, str(exc))
        return {"image_id": image_id, "status": "error", "error": str(exc)}
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


@celery_app.task(bind=True, name="app.queue.tasks.upload_from_url_task", max_retries=3)
def upload_from_url_task(
    self,
    image_id: str,
    image_url: str,
    folder_id: str,
    cloudinary_folder: str,
) -> Dict[str, Any]:
    import tempfile
    import requests
    from app.core.cloudinary import upload_file as cloudinary_upload
    import app.services.image_service as image_svc

    tmp_path = None
    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()

        suffix = os.path.splitext(image_url.split("?")[0])[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        result = cloudinary_upload(
            file_path=tmp_path,
            original_url=image_url,
            context={"image_id": image_id, "folder_id": folder_id},
        )
        if not result.uploaded:
            raise RuntimeError("Cloudinary upload failed")

        image_svc.update_image_after_upload(
            image_id=image_id,
            cloudinary_url=result.cloudinary_url,
            public_id=result.public_id,
            extra_metadata={},
            folder_id=folder_id,
        )
        return {"image_id": image_id, "status": "done", "cloudinary_url": result.cloudinary_url}
    except Exception as exc:
        logger.error("upload_from_url_task error (image=%s): %s", image_id, exc, exc_info=True)
        import app.services.image_service as image_svc
        image_svc.mark_image_error(image_id, folder_id, str(exc))
        return {"image_id": image_id, "status": "error", "error": str(exc)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass