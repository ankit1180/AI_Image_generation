"""
Application Configuration
==========================
All settings loaded from environment variables / .env file.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Backend root directory (backend/)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # App
    # ------------------------------------------------------------------
    APP_NAME: str = "AI Image Studio"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    FORCE_MOCK_MODEL: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ------------------------------------------------------------------
    # AI Model
    # ------------------------------------------------------------------
    MODEL_ID: str = "emilianJR/epiCRealism"
    DEVICE: str = "cpu"
    TORCH_DTYPE: str = "float32"

    # ------------------------------------------------------------------
    # Image Settings
    # ------------------------------------------------------------------
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    UPLOAD_CHUNK_SIZE: int = 1024 * 1024
    CLEANUP_LOCAL_FILES: bool = True
    OUTPUT_IMAGE_SIZE: int = 640
    DEFAULT_STRENGTH: float = 0.7
    DEFAULT_GUIDANCE_SCALE: float = 7.5

    # Prompts that describe a full scene/background/outfit rebuild (posters,
    # stadiums, cyberpunk, action shots) need much more denoising freedom
    # than a subtle style filter on an otherwise-unchanged portrait — one
    # global strength value can't serve both well. See prompt_loader's
    # folder-name heuristic for how this gets picked per prompt.
    SCENE_STRENGTH: float = 0.85

    # Strength previously used for a diffusion-based "same image" attempt.
    # No longer used: "Generate Same Image" now runs a true pixel-level
    # face swap (see face_swap.py) instead of SD1.5 img2img, so there's no
    # repaint-strength knob for that mode anymore. Left in place only so
    # older img_prompt.json overrides / .env values don't hard-fail.
    FACESWAP_STRENGTH: float = 0.3

    # ------------------------------------------------------------------
    # Face swap ("Generate Same Image" mode) — insightface's inswapper
    # ------------------------------------------------------------------
    # inswapper detects the face region on the sample image and replaces
    # just those pixels with a warped version of the user's face, leaving
    # every other pixel of the sample untouched. This is a completely
    # separate, non-diffusion pipeline from generate_similar()'s SD1.5
    # img2img — see app/services/face_swap.py.
    #
    # insightface's own `download=True` auto-fetch is broken (the official
    # GitHub release asset 404s — see deepinsight/insightface#2306/#2385),
    # so we download+cache the weights ourselves from a well-known mirror.
    # Override via env var if you'd rather point at your own mirror.
    INSWAPPER_MODEL_URL: str = (
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx"
    )
    INSWAPPER_MODEL_PATH: Path = BASE_DIR / "weights" / "inswapper_128.onnx"
    # face_swap.py IS the live "Generate Same Image" pipeline — see
    # generator.generate_same(), which calls face_swap.swap_face()
    # directly. (An earlier plan to instead use ControlNet + inpainting +
    # a full-body IP-Adapter for this mode was never implemented — no
    # app/services/body_transfer.py exists in this codebase — so those
    # settings have been removed from here to avoid confusion.)

    # ------------------------------------------------------------------
    # LCM-LoRA fast-inference settings (used when generator.lcm_active)
    # 4 steps / 1.5 guidance was tuned for CPU inference speed. On GPU
    # there's no need to be that aggressive — a few extra steps costs
    # almost nothing in wall-clock time and noticeably improves detail
    # and prompt adherence.
    # ------------------------------------------------------------------
    LCM_STEPS: int = 8
    LCM_GUIDANCE_SCALE: float = 1.9

    # ------------------------------------------------------------------
    # Face preservation (IP-Adapter)
    # ------------------------------------------------------------------
    USE_IP_ADAPTER: bool = True
    IP_ADAPTER_SCALE: float = 0.8

    # When True, use IP-Adapter-FaceID (ArcFace recognition embedding via
    # insightface) instead of the old ip-adapter-full-face_sd15 (CLIP image
    # embedding). ArcFace is trained specifically to distinguish identities,
    # so it holds up much better than CLIP's general "what does this look
    # like" embedding — CLIP was never trained to preserve who a face
    # belongs to. If insightface/the FaceID weights fail to load for any
    # reason, generator.py falls back to the old full-face adapter
    # automatically, so this is safe to leave on.
    USE_FACEID_ADAPTER: bool = True
    IP_ADAPTER_FACEID_REPO: str = "h94/IP-Adapter-FaceID"
    IP_ADAPTER_FACEID_WEIGHT_NAME: str = "ip-adapter-faceid_sd15.bin"
    IP_ADAPTER_FACEID_LORA_WEIGHT_NAME: str = "ip-adapter-faceid_sd15_lora.safetensors"
    # insightface model pack used for face detection + ArcFace embedding.
    # "buffalo_l" is the standard general-purpose pack; runs fine on CPU.
    INSIGHTFACE_MODEL_PACK: str = "buffalo_l"

    # ------------------------------------------------------------------
    # Face restoration (post-process pass)
    # ------------------------------------------------------------------
    # Diffusion + adapters still leave small artifacts around eyes/mouth
    # that read as "AI-generated weirdness" even when identity matches.
    # GFPGAN is a lightweight, CPU-friendly face-restoration model that
    # cleans this up as a final pass on the saved output. Non-fatal if the
    # weights fail to download/load — falls back to the un-restored image.
    USE_FACE_RESTORATION: bool = True
    GFPGAN_MODEL_URL: str = (
        "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
    )
    GFPGAN_UPSCALE: int = 1  # 1 = restore only, no upscaling (keeps OUTPUT_IMAGE_SIZE)



    # ------------------------------------------------------------------
    # Real-ESRGAN post-process upscale pass (runs after GFPGAN, on the
    # final composited image — sharpens detail without changing identity,
    # since it's a general super-resolution model, not a diffusion repaint).
    # ------------------------------------------------------------------
    USE_UPSCALER: bool = True
    REALESRGAN_MODEL_URL: str = (
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
    )
    # The model itself is a fixed 4x network; UPSCALE_FACTOR is the actual
    # output multiplier we request (RealESRGANer downsamples the raw 4x
    # result to hit this, so it doesn't have to be 4). 2x on top of a
    # 512px generation gives a 1024px final image without the artifact
    # risk of pushing SD1.5's own generation resolution up.
    UPSCALE_FACTOR: int = 2

    # When True: the folder's sample/preview image (from img_prompt.json)
    # is used as the img2img BASE — its pose/background/composition are
    # what gets kept — and the user's uploaded photo is only used as the
    # IP-Adapter face reference. This is "keep the sample's pose, swap in
    # my face" instead of the default "keep my pose, restyle it".
    USE_SAMPLE_AS_BASE: bool = True

    # Applied to every real (non-mock) generation unless a prompt entry
    # in img_prompt.json sets its own "negative_prompt" key.
    DEFAULT_NEGATIVE_PROMPT: str = (
        "deformed, disfigured, extra limbs, extra fingers, fused fingers, "
        "mutated hands, bad anatomy, bad proportions, cross-eyed, "
        "blurry, out of focus, low quality, low resolution, jpeg artifacts, "
        "watermark, text, signature, cartoon, anime, 3d render, cgi"
    )

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------
    STATIC_DIR: Path = BASE_DIR / "static"
    SAMPLE_DIR: Path = BASE_DIR / "static" / "samples"
    OUTPUT_DIR: Path = BASE_DIR / "static" / "outputs"
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    SAMPLE_CACHE_DIR: Path = BASE_DIR / "static" / "sample_cache"

    # ------------------------------------------------------------------
    # Data files
    # ------------------------------------------------------------------
    IMG_PROMPT_FILE: Path = BASE_DIR.parent / "img_prompt.json"

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "ai_img_studio"

    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = None
    CLOUDINARY_FOLDER: str = "ai-img-studio"

    # ------------------------------------------------------------------
    # Cache TTLs (seconds)  ← previously missing, caused AttributeError
    # ------------------------------------------------------------------
    CACHE_TTL_FOLDERS: int = 300        # 5 minutes
    CACHE_TTL_IMAGES: int = 120         # 2 minutes
    CACHE_TTL_IMAGE_DETAIL: int = 60    # 1 minute

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    RATE_LIMIT_GENERATE: str = "10/minute"  # max requests per IP per minute

    # ------------------------------------------------------------------
    # JSON DB (for image management service layer)
    # ------------------------------------------------------------------
    DB_PATH: str = str(BASE_DIR / "db" / "database.json")
    PROMPT_API_SECRET: str = "change-me-in-production"

    # ------------------------------------------------------------------
    # App title alias (used by some modules)
    # ------------------------------------------------------------------
    APP_TITLE: str = "AI Image Studio"

    # ------------------------------------------------------------------
    # Celery (optional – only needed when CELERY_ALWAYS_EAGER=False)
    # ------------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_ALWAYS_EAGER: bool = True  # run tasks synchronously by default (no worker needed)

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"),
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()


def create_directories() -> None:
    """Create required directories on startup."""
    settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
    settings.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.SAMPLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    settings.INSWAPPER_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)


create_directories()


# Compatibility alias used by older service modules
def get_settings() -> Settings:
    return settings