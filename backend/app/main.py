"""
Application Entry Point
========================
Run:
    uvicorn app.main:app --reload

API Docs:
    http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.folders import router as folders_router
from app.api.generate import router as generate_router
from app.api.gallery import router as gallery_router
#from app.api.images import router as images_router
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description=(
        "AI Image Generation Platform. "
        "Users interact with folders and preview images only; "
        "prompts are kept private on the server."
    ),
)

# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Static Files
# ------------------------------------------------------------------
app.mount("/static/outputs", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="outputs")
app.mount("/static/samples", StaticFiles(directory=str(settings.SAMPLE_DIR)), name="samples")

# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------
app.include_router(folders_router)
app.include_router(generate_router)
app.include_router(gallery_router)
##app.include_router(images_router)
app.include_router(health_router)
app.include_router(tasks_router)


# ------------------------------------------------------------------
# Startup
# ------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    # Reload prompt_loader so it picks up any changes to img_prompt.json
    from app.services.prompt_loader import prompt_loader
    prompt_loader.reload()


# ------------------------------------------------------------------
# Root
# ------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"{settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "folders": "/folders",
            "folder_detail": "/folders/{folder_id}",
            "generate_similar": "POST /generate/similar",
            "generate_same": "POST /generate/same",
            "generation_status": "/generation/{task_id}",
            "gallery": "/gallery",
            "images": "/images",
        },
    }