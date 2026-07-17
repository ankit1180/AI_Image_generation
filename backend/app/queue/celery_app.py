"""
Celery application instance for backend/app.
"""

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings


def create_celery_app() -> Celery:
    app = Celery(
        "ai_img_trans",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
        include=["app.queue.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        result_expires=3600,
        # When True, tasks run inline (no worker/Redis needed for execution)
        task_always_eager=settings.CELERY_ALWAYS_EAGER,
        task_eager_propagates=True,
    )
    return app


celery_app = create_celery_app()


# ---------------------------------------------------------------------------
# Preload the generation model when a worker process boots, instead of
# lazily on the first real generation request.
#
# Without this, the very first user to hit /generate after a worker
# (re)start pays the full cost of downloading + loading the base SD model
# and the LCM-LoRA weights as part of their request — easily minutes,
# which blows past any reasonable frontend timeout. By warming the model
# here, that cost is paid once at worker startup, before any task is
# accepted, so every real generation request only pays the fast LCM
# inference cost.
#
# This only fires when running an actual Celery worker process. It will
# NOT fire in eager mode (CELERY_ALWAYS_EAGER=True), since eager mode
# runs tasks inline in whatever process called apply_async() (e.g. your
# FastAPI server) rather than in a dedicated worker process — there is no
# separate "worker boot" event to hook into in that mode.
# ---------------------------------------------------------------------------
@worker_process_init.connect
def preload_generation_model(**kwargs) -> None:
    if settings.FORCE_MOCK_MODEL:
        print("[Celery] FORCE_MOCK_MODEL is set — skipping model preload.")
        return

    try:
        # Imported here (not at module top) to avoid circular imports and
        # to make sure heavy ML libraries are only imported inside the
        # actual worker process, not the main FastAPI/Celery app process.
        from app.services.generator import generator

        print("[Celery] Preloading generation model in worker process...")
        generator._load_model()
        print("[Celery] Model preload complete. Worker ready for tasks.")
    except Exception as exc:
        # Don't crash worker startup if preload fails — the lazy-load
        # fallback in generator.generate() will still attempt to load
        # the model on first use (or fall back to mock mode).
        print(f"[Celery] Model preload failed (will lazy-load on first task): {exc}")