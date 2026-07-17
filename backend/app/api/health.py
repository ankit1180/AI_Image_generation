from fastapi import APIRouter
import redis as redis_lib
from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", summary="System health check")
async def health():
    settings = get_settings()
    checks = {"api": "ok", "redis": "unknown", "db": "unknown"}

    # Redis check
    try:
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # DB file check
    import os
    checks["db"] = "ok" if os.path.exists(settings.DB_PATH) else "no db file yet (will be created on first write)"

    overall = "ok" if all(v == "ok" or "no db" in str(v) for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}