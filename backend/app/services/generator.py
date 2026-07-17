"""
Generator Service
=================
Converts a user image + prompt config into an AI-transformed output image.

The prompt_config dict is passed in from the Celery worker.
This service has no concept of prompt IDs or database – it only deals with
images and prompt strings (which flow in, are used, and are never stored here).

LCM-LoRA integration
---------------------
To make CPU inference fast enough to be usable, the base SD1.5 pipeline is
patched with an LCM scheduler + the official LCM-LoRA weights
("latent-consistency/lcm-lora-sdv1-5"). This lets generation converge in
~4 steps instead of the usual 25-50, with a low guidance scale (~1.0-2.0).

If the LCM-LoRA weights fail to load for any reason (no network, bad cache,
etc.), the pipeline silently falls back to running the base model with
normal step counts/guidance — slower, but still correct — rather than
crashing the whole generation pipeline.
"""

from __future__ import annotations
import hashlib
import math
import re
from app.core.config import settings
from pathlib import Path
from typing import Any
from uuid import uuid4


print("DEVICE FROM CONFIG:", settings.DEVICE)

try:
    import torch
    from diffusers import AutoPipelineForImage2Image, AutoencoderKL, LCMScheduler
    DIFFUSERS_AVAILABLE = True
except Exception as e:
    print(f"[Generator] Diffusers unavailable: {e}")
    torch = None
    AutoPipelineForImage2Image = None
    LCMScheduler = None
    DIFFUSERS_AVAILABLE = False

# insightface gives us the ArcFace face-recognition embedding that
# IP-Adapter-FaceID conditions on. This is a lightweight detector+embedder
# (not a diffusion model) — cheap to run on CPU. Optional: if it's not
# installed or its model pack fails to download, we fall back to the old
# CLIP-based full-face adapter further down.
try:
    import cv2
    import numpy as np
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except Exception as e:
    print(f"[Generator] insightface unavailable: {e}")
    cv2 = None
    np = None
    FaceAnalysis = None
    INSIGHTFACE_AVAILABLE = False

# GFPGAN cleans up small facial artifacts (eyes/mouth) left behind by
# diffusion + adapters. Optional, non-fatal post-process pass.
try:
    from gfpgan import GFPGANer
    GFPGAN_AVAILABLE = True
except Exception as e:
    print(f"[Generator] GFPGAN unavailable: {e}")
    GFPGANer = None
    GFPGAN_AVAILABLE = False

from PIL import Image

from app.core.config import settings


def _fetch_sample_image(url: str) -> Image.Image | None:
    """
    Download (and cache) the folder's sample/preview image so it can be
    used as the img2img BASE instead of the user's upload. Returns None
    on any failure so callers can fall back to the user's photo instead
    of crashing the whole generation.
    """
    if not url:
        return None

    try:
        import requests

        cache_key = hashlib.sha1(url.encode()).hexdigest()
        ext = Path(url.split("?")[0]).suffix or ".jpg"
        cache_path = settings.SAMPLE_CACHE_DIR / f"{cache_key}{ext}"

        if not cache_path.exists():
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)

        return Image.open(cache_path).convert("RGB")
    except Exception as exc:
        print(f"[Generator] Failed to fetch sample base image ({url}): {exc}")
        return None

# Official LCM-LoRA weights compatible with SD1.5-family base models.
LCM_LORA_ID = "latent-consistency/lcm-lora-sdv1-5"

# SD1.5's CLIP text encoder hard-truncates at 77 tokens (~40-50 words
# depending on punctuation). Anything past that is silently dropped by
# the tokenizer — the model never sees it. Our prompts average 150+
# words because they were written for a different kind of tool (an
# instruction-following image editor, not an SD1.5 img2img pipeline),
# so without trimming, most of the scene/background/lighting description
# never reaches the model at all. 75 words (~100-110 tokens with SD1.5's
# tokenizer) still gets truncated occasionally on verbose prompts, but
# captures far more of the scene than the old 45-word cut did.
_MAX_PROMPT_WORDS = 75

# Boilerplate clauses like "Take Face From Uploaded image Keep same 100%"
# describe an identity-preservation instruction that plain SD1.5 img2img
# can't actually honor — it has no concept of "this specific face". Since
# every prompt has one, keeping it just wastes token budget that would
# otherwise go to visual descriptors the model *can* act on.
_BOILERPLATE_PATTERNS = (
    r"take\s+face\s+from\s+uploaded\s+image[^.]*\.?",
    r"take\s+only\s+face\s+from\s+uploaded\s+image[^.]*\.?",
    r"face\s+should\s+be\s+matching[^.]*\.?",
    r"keep\s+same\s+100\s*(?:%|percent)",
)

# SD1.5 was trained on web image/caption pairs where "girl"/"young girl"
# overwhelmingly correlates with actual children — it has no way to read
# "young girl" as the casual "young woman" sense these prompts intend
# (obvious from the folders' own preview images, which show adult models).
# Left alone, this reliably produces a child instead of the intended
# adult subject, regardless of strength/steps/guidance tuning. We swap
# it to unambiguous language, but must NOT touch literal sign/prop text
# like "says 'Birthday Girl'" — that apostrophe right after the word is
# the signal it's quoted prop text, not a subject description.
_AGE_WORD_MAP = {
    "girls": "women", "Girls": "Women", "GIRLS": "WOMEN",
    "girl": "woman", "Girl": "Woman", "GIRL": "WOMAN",
}
_AGE_WORD_PATTERN = re.compile(
    r"\b(girls?|GIRLS?)\b(?!')"
)


def _debias_age_language(text: str) -> str:
    return _AGE_WORD_PATTERN.sub(lambda m: _AGE_WORD_MAP.get(m.group(0), m.group(0)), text)


def _compress_prompt(prompt_text: str, max_words: int = _MAX_PROMPT_WORDS) -> str:
    """Strip un-actionable boilerplate and de-bias age language, then trim
    to fit SD1.5's 77-token CLIP budget so the words that matter
    (background, outfit, lighting, style) don't get silently truncated
    away, and the model doesn't render a child when an adult was meant."""
    text = _debias_age_language(prompt_text)
    for pattern in _BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.")

    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])
    return text

def get_device():
    if torch is not None and torch.cuda.is_available():
        return "cuda"
    return "cpu"


# -----------------------------------------------------------------------
# Face embedding (for IP-Adapter-FaceID)
# -----------------------------------------------------------------------

_face_analysis_app = None  # lazy singleton, loaded on first use


def _get_face_analysis_app():
    """Lazily load and cache the insightface FaceAnalysis app."""
    global _face_analysis_app
    if _face_analysis_app is not None:
        return _face_analysis_app
    if not INSIGHTFACE_AVAILABLE:
        return None
    try:
        app = FaceAnalysis(name=settings.INSIGHTFACE_MODEL_PACK)
        # ctx_id=-1 forces CPU; insightface has no notion of the app's own
        # torch device setting, so this is independent of get_device().
        ctx_id = 0 if get_device() == "cuda" else -1
        app.prepare(ctx_id=ctx_id, det_size=(640, 640))
        _face_analysis_app = app
        print(f"[Generator] insightface '{settings.INSIGHTFACE_MODEL_PACK}' loaded.")
        return app
    except Exception as exc:
        print(f"[Generator] Failed to load insightface model pack: {exc}")
        return None


def get_face_embedding(image: "Image.Image"):
    """
    Extract an ArcFace identity embedding from the uploaded photo, for use
    with IP-Adapter-FaceID. Returns None (never raises) if insightface is
    unavailable, the model pack failed to load, or no face is detected —
    callers must fall back to the plain image-based adapter in that case.
    """
    if not INSIGHTFACE_AVAILABLE:
        return None

    app = _get_face_analysis_app()
    if app is None:
        return None

    try:
        img_bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        faces = app.get(img_bgr)
        if not faces:
            print("[Generator] No face detected in uploaded photo for FaceID embedding.")
            return None
        # If multiple faces are present, use the largest (most likely the
        # intended subject rather than someone in the background).
        faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
        return faces[0].normed_embedding
    except Exception as exc:
        print(f"[Generator] Face embedding extraction failed: {exc}")
        return None


# -----------------------------------------------------------------------
# Face restoration (GFPGAN post-process pass)
# -----------------------------------------------------------------------

_gfpgan_restorer = None  # lazy singleton
_gfpgan_load_failed = False


def _get_gfpgan_restorer():
    """Lazily load and cache the GFPGAN restorer. Downloads weights to
    GFPGAN's default cache dir on first use if not already present."""
    global _gfpgan_restorer, _gfpgan_load_failed
    if _gfpgan_restorer is not None:
        return _gfpgan_restorer
    if not GFPGAN_AVAILABLE or _gfpgan_load_failed:
        return None
    try:
        _gfpgan_restorer = GFPGANer(
            model_path=settings.GFPGAN_MODEL_URL,
            upscale=settings.GFPGAN_UPSCALE,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=None,  # background upsampling not needed; face-only pass
        )
        print("[Generator] GFPGAN restorer loaded.")
        return _gfpgan_restorer
    except Exception as exc:
        print(f"[Generator] Failed to load GFPGAN: {exc} – skipping face restoration.")
        _gfpgan_load_failed = True
        return None


def restore_face(image: "Image.Image") -> "Image.Image":
    """
    Run a GFPGAN restoration pass on a generated image to clean up small
    facial artifacts left behind by diffusion + adapters. Returns the
    original image unchanged (never raises) if GFPGAN is unavailable, its
    weights fail to load, or restoration errors out for any reason.
    """
    if not settings.USE_FACE_RESTORATION:
        return image

    restorer = _get_gfpgan_restorer()
    if restorer is None:
        return image

    try:
        img_bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        _, _, restored_bgr = restorer.enhance(
            img_bgr,
            has_aligned=False,
            only_center_face=False,
            paste_back=True,
        )
        restored_rgb = cv2.cvtColor(restored_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(restored_rgb)
    except Exception as exc:
        print(f"[Generator] GFPGAN restoration failed (non-fatal): {exc}")
        return image


# -----------------------------------------------------------------------
# Upscaling (Real-ESRGAN post-process pass)
# -----------------------------------------------------------------------

_realesrgan_upscaler = None  # lazy singleton
_realesrgan_load_failed = False

try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    REALESRGAN_AVAILABLE = True
except ImportError:
    REALESRGAN_AVAILABLE = False


def _get_realesrgan_upscaler():
    """Lazily load and cache the Real-ESRGAN upscaler. Downloads weights
    to basicsr's default cache dir on first use if not already present."""
    global _realesrgan_upscaler, _realesrgan_load_failed
    if _realesrgan_upscaler is not None:
        return _realesrgan_upscaler
    if not REALESRGAN_AVAILABLE or _realesrgan_load_failed:
        return None
    try:
        # RealESRGAN_x4plus is a fixed 4x network — RealESRGANer's `scale`
        # here is what its internal tiling/padding math uses, NOT the
        # final output size. The output size is controlled per-call via
        # `outscale` in upscale_image() below, so this stays 4 regardless
        # of settings.UPSCALE_FACTOR.
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=23, num_grow_ch=32, scale=4,
        )
        _realesrgan_upscaler = RealESRGANer(
            scale=4,
            model_path=settings.REALESRGAN_MODEL_URL,
            model=model,
            tile=0,  # 0 = no tiling; fine at our image sizes on a 4050
            tile_pad=10,
            pre_pad=0,
            half=(get_device() == "cuda"),  # fp16 on GPU, fp32 on CPU
        )
        print("[Generator] Real-ESRGAN upscaler loaded.")
        return _realesrgan_upscaler
    except Exception as exc:
        print(f"[Generator] Failed to load Real-ESRGAN: {exc} – skipping upscale.")
        _realesrgan_load_failed = True
        return None


def upscale_image(image: "Image.Image") -> "Image.Image":
    """
    Run a Real-ESRGAN super-resolution pass on the final (already
    face-restored) image. Returns the original image unchanged (never
    raises) if Real-ESRGAN is unavailable, its weights fail to load, or
    upscaling errors out for any reason — same non-fatal pattern as
    restore_face().
    """
    if not settings.USE_UPSCALER:
        return image

    upscaler = _get_realesrgan_upscaler()
    if upscaler is None:
        return image

    try:
        img_bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        upscaled_bgr, _ = upscaler.enhance(img_bgr, outscale=settings.UPSCALE_FACTOR)
        upscaled_rgb = cv2.cvtColor(upscaled_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(upscaled_rgb)
    except Exception as exc:
        print(f"[Generator] Real-ESRGAN upscaling failed (non-fatal): {exc}")
        return image

class GeneratorService:
    """Singleton image generation service (lazy model load)."""

    def __init__(self) -> None:
        self.pipeline = None
        self.fallback_active = False
        self.lcm_active = False  # True once LCM scheduler + LoRA are successfully attached
        self.ip_adapter_active = False  # True once IP-Adapter weights are attached
        self.faceid_active = False  # True once IP-Adapter-FaceID (ArcFace) specifically is active
        self.dtype = None  # set once the base model is loaded (see _load_model)

    def _load_model(self) -> None:
        if not DIFFUSERS_AVAILABLE:
            print("[Generator] Diffusers unavailable – running in MOCK mode.")
            self.fallback_active = True
            return

        if self.pipeline is not None or self.fallback_active:
            return

        device = get_device()  # actual detected hardware — source of truth

        if settings.DEVICE == "cuda" and device == "cpu":
            print(
                "[Generator] WARNING: DEVICE=cuda in config but no CUDA GPU "
                "was detected by torch — falling back to CPU/float32. "
                "Check nvidia-smi / your torch install if this is unexpected."
            )

        # dtype must follow the REAL device, not the configured one — fp16
        # on an actual CPU device will error out or silently misbehave.
        if device == "cuda" and settings.TORCH_DTYPE == "float16":
            dtype = torch.float16
        else:
            dtype = torch.float32
        self.dtype = dtype  # cached so generate() can match embedding tensors to it

        print(f"[Generator] Loading {settings.MODEL_ID} on {device} (dtype={dtype})...")
        try:
            pipeline = AutoPipelineForImage2Image.from_pretrained(
                settings.MODEL_ID,
                torch_dtype=dtype,
                safety_checker=None,
                requires_safety_checker=False,
            )
            pipeline.to(device)
            print("[Generator] Base model loaded successfully.")
        except Exception as exc:
            print(f"[Generator] Model load failed: {exc} – switching to MOCK mode.")
            self.pipeline = None
            self.fallback_active = True
            return

        # --- Swap in the fp16-stable VAE ---
        # SD1.5's original VAE is numerically unstable in float16 — it's
        # prone to clipped/blown-out values during latent decoding, which
        # shows up as washed-out, hazy, low-contrast output (especially in
        # scenes with strong light sources). stabilityai/sd-vae-ft-mse was
        # retrained specifically to be stable under fp16 and is the
        # standard fix for this. Non-fatal if it fails to load — falls
        # back to the base pipeline's default VAE.
        if dtype == torch.float16:
            try:
                fixed_vae = AutoencoderKL.from_pretrained(
                    "stabilityai/sd-vae-ft-mse",
                    torch_dtype=dtype,
                )
                pipeline.vae = fixed_vae.to(device)
                print("[Generator] Swapped in sd-vae-ft-mse for fp16 stability.")
            except Exception as exc:
                print(f"[Generator] Failed to load fixed VAE: {exc} – using default VAE.")

        # Assign immediately so self.pipeline reflects the real state right
        # after a successful load — the LCM-LoRA step below is optional and
        # must not gate whether the base pipeline is considered "loaded".
        self.pipeline = pipeline

        # --- Attach LCM scheduler + LCM-LoRA weights for fast CPU inference ---
        try:
            print(f"[Generator] Loading LCM-LoRA weights ({LCM_LORA_ID})...")
            pipeline.scheduler = LCMScheduler.from_config(pipeline.scheduler.config)
            pipeline.load_lora_weights(LCM_LORA_ID)
            # Fuse the LoRA into the base weights so generation runs at full
            # speed without the runtime overhead of separate LoRA adapter math.
            pipeline.fuse_lora()
            self.lcm_active = True
            print("[Generator] LCM-LoRA attached and fused successfully.")
        except Exception as exc:
            # Not fatal — fall back to the base pipeline with normal
            # scheduler/steps/guidance. Generation will just be slower.
            print(f"[Generator] LCM-LoRA load failed: {exc} – using base scheduler (slower).")
            self.lcm_active = False

        # --- Attach IP-Adapter for face preservation ---
        # img2img "strength" alone trades off style vs. identity along a
        # single knob — turn it down enough to keep the face and you also
        # lose most of the costume/background change the prompts are
        # supposed to produce. IP-Adapter conditions the model on the
        # uploaded photo's face directly (via a CLIP image embedding fed
        # in alongside the text prompt), so identity holds up even at the
        # higher strengths needed to actually change the scene.
        if settings.USE_IP_ADAPTER:
            self.faceid_active = False
            loaded = False

            # --- Preferred: IP-Adapter-FaceID (ArcFace embedding) ---
            # Only worth attempting if insightface is actually available;
            # otherwise there's no way to produce the embedding it needs.
            if settings.USE_FACEID_ADAPTER and INSIGHTFACE_AVAILABLE:
                try:
                    print("[Generator] Loading IP-Adapter-FaceID weights...")
                    pipeline.load_ip_adapter(
                        settings.IP_ADAPTER_FACEID_REPO,
                        subfolder="",
                        weight_name=settings.IP_ADAPTER_FACEID_WEIGHT_NAME,
                        image_encoder_folder=None,
                    )
                    pipeline.set_ip_adapter_scale(settings.IP_ADAPTER_SCALE)
                    self.ip_adapter_active = True
                    self.faceid_active = True
                    loaded = True
                    print("[Generator] IP-Adapter-FaceID attached successfully.")
                except Exception as exc:
                    print(
                        f"[Generator] IP-Adapter-FaceID load failed: {exc} "
                        "– falling back to the CLIP-based full-face adapter."
                    )

            # --- Fallback: original CLIP-based full-face adapter ---
            if not loaded:
                try:
                    print("[Generator] Loading IP-Adapter (face) weights...")
                    pipeline.load_ip_adapter(
                        "h94/IP-Adapter",
                        subfolder="models",
                        weight_name="ip-adapter-full-face_sd15.bin",
                    )
                    pipeline.set_ip_adapter_scale(settings.IP_ADAPTER_SCALE)
                    self.ip_adapter_active = True
                    print("[Generator] IP-Adapter (CLIP full-face) attached successfully.")
                except Exception as exc:
                    # Not fatal — generation still runs, just without the extra
                    # face-conditioning signal (falls back to strength-only).
                    print(f"[Generator] IP-Adapter load failed: {exc} – continuing without it.")
                    self.ip_adapter_active = False

        # --- Memory-saving slicing ---
        # enable_attention_slicing() doesn't just save VRAM — it REPLACES
        # every attention processor in the UNet with a generic sliced one.
        # If IP-Adapter is active, that wipes out the specialized processors
        # load_ip_adapter() just installed (regardless of call order), so the
        # pipeline ends up feeding image-conditioning data to a processor
        # that doesn't understand it -> "'tuple' object has no attribute
        # 'shape'" deep inside the UNet. The two features are mutually
        # exclusive; skip attention slicing whenever IP-Adapter is active.
        # (VAE slicing is unrelated to attention processors and is always
        # safe to enable.)
        if device == "cuda":
            try:
                pipeline.enable_vae_slicing()
                if not self.ip_adapter_active:
                    pipeline.enable_attention_slicing()
                else:
                    print(
                        "[Generator] Skipping attention slicing (IP-Adapter "
                        "active — the two are incompatible; not needed on "
                        "GPU at this step count anyway)."
                    )
            except Exception as exc:
                print(f"[Generator] Attention/VAE slicing setup failed (non-fatal): {exc}")

    # -------------------------------------------------------------------
    # Public entry points — one per generation mode. Each owns its own
    # base-image selection / strength policy; they share only the
    # low-level pipeline mechanics via _run_diffusion_pipeline(). Note:
    # generate_same() below does NOT use this at all — it's a completely
    # separate, non-diffusion face-swap pipeline (see face_swap.py).
    # -------------------------------------------------------------------

    def generate_similar(
        self,
        image_path: str | Path,
        prompt_config: dict[str, Any],
    ) -> str:
        """
        "Generate Similar Image" mode (the original, default pipeline —
        restored to match pre-upgrade behavior).

        Base image selection honors settings.USE_SAMPLE_AS_BASE, exactly
        as the single-button pipeline did before "Generate Same Image"
        was split out as a separate mode:

          USE_SAMPLE_AS_BASE=True (the default)  → base = the folder's
            sample/preview image. Its pose/background/composition are
            what the prompt was written to describe, and the user's
            face is layered on top via IP-Adapter FaceID.

          USE_SAMPLE_AS_BASE=False → base = the user's own uploaded
            photo, restyled toward the prompt.

        Either way, `strength` (from img_prompt.json / folder defaults)
        controls how much of the base actually gets repainted, and the
        prompt is always used.

        Parameters
        ----------
        image_path   : path to the user's uploaded image
        prompt_config: dict containing at minimum {"prompt": "..."}.
                       Loaded by the caller from prompt_loader (internal).

        Returns
        -------
        Relative output URL string (e.g. "/static/outputs/abc.png")
        """
        user_image = Image.open(image_path).convert("RGB").resize(
            (settings.OUTPUT_IMAGE_SIZE, settings.OUTPUT_IMAGE_SIZE)
        )
        strength = float(prompt_config.get("strength", settings.DEFAULT_STRENGTH))

        used_sample_base = bool(settings.USE_SAMPLE_AS_BASE)
        base_image = user_image
        if used_sample_base:
            sample_url = prompt_config.get("sample_image_url")
            sample_image = _fetch_sample_image(sample_url) if sample_url else None
            if sample_image is not None:
                base_image = sample_image.resize(
                    (settings.OUTPUT_IMAGE_SIZE, settings.OUTPUT_IMAGE_SIZE)
                )
            else:
                # Sample couldn't be loaded — degrade gracefully to the
                # user's own photo rather than failing the generation.
                print(
                    "[Generator] generate_similar: sample base image "
                    "unavailable, falling back to the user's uploaded photo."
                )
                used_sample_base = False

        return self._run_diffusion_pipeline(
            prompt_config=prompt_config,
            base_image=base_image,
            face_reference_image=user_image,
            strength=strength,
            used_sample_base=used_sample_base,
        )

    def generate_same(
        self,
        image_path: str | Path,
        prompt_config: dict[str, Any],
    ) -> str:
        """
        "Generate Same Image" mode (face-swap-only / "Keep Same Background").

        Unlike generate_similar(), this does NOT run the SD1.5 diffusion
        pipeline at all. It performs a true pixel-level face swap (see
        app/services/face_swap.py, insightface's inswapper model): the
        folder's sample/preview image is used almost exactly as-is — every
        pixel outside the face region is untouched — and only the face is
        replaced with the user's uploaded photo. This guarantees the
        background, outfit, and pose genuinely stay the same, which a
        low-strength img2img repaint could only approximate.

        Parameters
        ----------
        image_path   : path to the user's uploaded image
        prompt_config: dict containing "sample_image_url" (the folder's
                       preview image). The prompt text itself is not used
                       in this mode — there's no diffusion generation step.

        Returns
        -------
        Relative output URL string (e.g. "/static/outputs/abc.png")

        Raises
        ------
        RuntimeError if the sample image can't be loaded, or if the face
        swap fails (e.g. no detectable face in either image) — the Celery
        task catches this and reports a clear failure instead of silently
        returning a wrong result.
        """
        user_image = Image.open(image_path).convert("RGB")

        sample_url = prompt_config.get("sample_image_url")
        sample_image = _fetch_sample_image(sample_url) if sample_url else None
        if sample_image is None:
            raise RuntimeError(
                "Generate Same Image requires this style's sample image, "
                "but it could not be loaded."
            )

        # Deferred import: face_swap.py imports several names back out of
        # this module (INSIGHTFACE_AVAILABLE, get_device,
        # _get_face_analysis_app) at ITS module-import time, so importing
        # it here — after this module has already finished loading —
        # avoids a circular import.
        from app.services.face_swap import swap_face

        swapped = swap_face(sample_image, user_image)
        if swapped is None:
            raise RuntimeError(
                "Face swap failed — make sure both the style's sample "
                "image and your uploaded photo have a clearly visible face."
            )

        # Same post-process cleanup pass used by generate_similar(): fixes
        # small blend-seam/compression artifacts left behind by the swap.
        # Non-fatal / no-op if GFPGAN or the upscaler are off or unavailable.
        result = restore_face(swapped)
        result = upscale_image(result)

        filename = f"{uuid4().hex}.png"
        output_path = settings.OUTPUT_DIR / filename
        result.save(output_path)

        print("=" * 60)
        print("generate_same: pixel face-swap pipeline (no diffusion)")
        print("face_restoration_enabled:", settings.USE_FACE_RESTORATION)
        print("upscaler_enabled:", settings.USE_UPSCALER)
        print("=" * 60)

        return f"/static/outputs/{filename}"

    # -------------------------------------------------------------------
    # Shared diffusion pipeline mechanics (used by generate_similar() only
    # — generate_same() above is a completely separate, non-diffusion
    # face-swap pipeline and never calls this).
    # -------------------------------------------------------------------

    def _run_diffusion_pipeline(
        self,
        prompt_config: dict[str, Any],
        base_image: "Image.Image",
        face_reference_image: "Image.Image",
        strength: float,
        used_sample_base: bool,
    ) -> str:
        prompt_text: str = prompt_config["prompt"]
        negative_prompt: str = prompt_config.get("negative_prompt", "")

        # The mock path does keyword matching on the full original text, so
        # keep that untouched. The real diffusion path gets the compressed,
        # CLIP-token-budget-aware version so it doesn't lose everything
        # past word ~45 to silent tokenizer truncation.
        compressed_prompt_text = _compress_prompt(prompt_text)

        user_image = face_reference_image
        image = base_image

        filename = f"{uuid4().hex}.png"
        output_path = settings.OUTPUT_DIR / filename

        use_mock = (
            settings.FORCE_MOCK_MODEL
            or not DIFFUSERS_AVAILABLE
            or self.fallback_active
        )

        if not use_mock:
            try:
                self._load_model()
            except Exception as exc:
                print(f"[Generator] Model load error: {exc} – falling back to MOCK.")
                self.fallback_active = True
                use_mock = True

        # use_mock may have flipped True inside _load_model() if the base
        # model itself failed to load (not just the LoRA).
        use_mock = use_mock or self.fallback_active

        # --- Pick step count / guidance scale based on whether LCM is active ---
        # NOTE: diffusers img2img only actually RUNS round(num_inference_steps
        # * strength) steps, not num_inference_steps itself. At strength=0.4
        # and a requested 6 steps, that's round(6*0.4)=2 real steps — far too
        # few for usable LCM output. We scale the requested count up so the
        # target step count is what actually executes, regardless of strength.
        if self.lcm_active:
            # LCM converges in very few steps; guidance scale should stay low.
            target_steps = int(
                prompt_config.get("lcm_steps", settings.LCM_STEPS)
            )
            num_inference_steps = max(
                target_steps,
                math.ceil(target_steps / max(strength, 0.05)),
            )
            guidance_scale = float(
                prompt_config.get("lcm_guidance_scale", settings.LCM_GUIDANCE_SCALE)
            )
        else:
            target_steps = int(prompt_config.get("num_inference_steps", 30))
            num_inference_steps = max(
                target_steps,
                math.ceil(target_steps / max(strength, 0.05)),
            )
            guidance_scale = float(
                prompt_config.get("guidance_scale", settings.DEFAULT_GUIDANCE_SCALE)
            )

        print("=" * 60)
        print("FORCE_MOCK_MODEL:", settings.FORCE_MOCK_MODEL)
        print("DIFFUSERS_AVAILABLE:", DIFFUSERS_AVAILABLE)
        print("fallback_active:", self.fallback_active)
        print("lcm_active:", self.lcm_active)
        print("ip_adapter_active:", self.ip_adapter_active)
        print("faceid_active:", self.faceid_active)
        print("face_restoration_enabled:", settings.USE_FACE_RESTORATION)
        print("used_sample_base:", used_sample_base)
        print("target_steps (LCM_STEPS/config):", target_steps)
        print("requested num_inference_steps (scaled for strength):", num_inference_steps,
              "guidance_scale:", guidance_scale, "strength:", strength)
        print("Original prompt words:", len(prompt_text.split()))
        print("Compressed prompt sent to model:", compressed_prompt_text)
        print("=" * 60)

        if use_mock:
            self._mock_generate(image, output_path, prompt_text)
        else:
            pipeline_kwargs: dict[str, Any] = dict(
                prompt=compressed_prompt_text,
                negative_prompt=negative_prompt,
                image=image,
                strength=strength,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
            )
            if self.ip_adapter_active:
                faceid_embeds = None
                if self.faceid_active:
                    # ArcFace embedding of the user's own uploaded photo —
                    # this is the face we're preserving, regardless of what
                    # the img2img base is. Falls back to the plain image
                    # input below if no face could be detected/embedded
                    # (e.g. low-quality upload), so a bad photo degrades
                    # gracefully instead of crashing generation.
                    embedding = get_face_embedding(user_image)
                    if embedding is not None:
                        pos_embeds = torch.from_numpy(embedding)\
                            .unsqueeze(0)\
                            .unsqueeze(0)\
                            .to(device=get_device(), dtype=getattr(self, "dtype", torch.float32))
                        
                        neg_embeds = torch.zeros_like(pos_embeds)
                        faceid_embeds = [torch.cat([neg_embeds,pos_embeds], dim=0)]

                if faceid_embeds is not None:
                    pipeline_kwargs["ip_adapter_image_embeds"] = faceid_embeds
                elif self.faceid_active:
                    # Pipelines loaded with the FaceID adapter have no CLIP
                    # image encoder attached (FaceID conditions purely on
                    # the ArcFace embedding), so passing a raw
                    # ip_adapter_image here would error out rather than
                    # degrade gracefully. With no embedding available
                    # (no face detected in the upload), the safest fallback
                    # is to skip IP-Adapter conditioning for this generation
                    # entirely — strength/prompt still apply normally.
                    print(
                        "[Generator] No FaceID embedding available for this "
                        "upload — generating without face conditioning."
                    )
                else:
                    # CLIP-based full-face adapter path: this DOES have an
                    # image encoder, so raw-image conditioning is valid here.
                    pipeline_kwargs["ip_adapter_image"] = user_image

            result = self.pipeline(**pipeline_kwargs).images[0]

            # Final cleanup pass: fix small facial artifacts left behind by
            # diffusion + adapters. Non-fatal / no-op if GFPGAN is off or
            # unavailable — see restore_face().
            result = restore_face(result)
            result = upscale_image(result)
            result.save(output_path)

        return f"/static/outputs/{filename}"

    # -----------------------------------------------------------------------
    # Mock generation (Pillow filters based on prompt keywords)
    # -----------------------------------------------------------------------

    def _mock_generate(
        self,
        image: Image.Image,
        output_path: Path,
        prompt_text: str,
    ) -> None:
        from PIL import ImageEnhance, ImageFilter, ImageOps

        p = prompt_text.lower()
        out = image.copy()

        if any(k in p for k in ("red carpet", "hollywood", "cinematic", "portrait")):
            out = ImageEnhance.Contrast(out).enhance(1.3)
            out = ImageEnhance.Color(out).enhance(1.1)
            r, g, b = out.split()
            out = Image.merge("RGB", (
                r.point(lambda i: min(255, int(i * 1.1))),
                g,
                b.point(lambda i: int(i * 0.9)),
            ))
        elif any(k in p for k in ("anime", "manga", "cartoon")):
            out = ImageEnhance.Color(out).enhance(1.6)
            out = ImageOps.posterize(out, 4)
            out = out.filter(ImageFilter.EDGE_ENHANCE_MORE)
        elif any(k in p for k in ("sketch", "pencil", "drawing")):
            out = ImageOps.grayscale(out)
            out = ImageOps.colorize(out, "#101010", "#ffffff")
            out = ImageEnhance.Contrast(out).enhance(1.4)
        elif any(k in p for k in ("watercolor", "painting", "art")):
            out = out.filter(ImageFilter.SMOOTH_MORE)
            out = ImageEnhance.Color(out).enhance(0.85)
            out = out.filter(ImageFilter.DETAIL)
        elif any(k in p for k in ("cyberpunk", "neon", "futuristic")):
            r, g, b = out.split()
            out = Image.merge("RGB", (
                r.point(lambda i: min(255, int(i * 1.3))),
                g.point(lambda i: int(i * 0.8)),
                b.point(lambda i: min(255, int(i * 1.4))),
            ))
            out = ImageEnhance.Contrast(out).enhance(1.25)
        elif any(k in p for k in ("vintage", "retro", "film", "diwali", "traditional")):
            out = ImageEnhance.Contrast(out).enhance(0.85)
            out = ImageEnhance.Color(out).enhance(0.9)
            r, g, b = out.split()
            out = Image.merge("RGB", (
                r.point(lambda i: min(255, int(i * 1.15))),
                g.point(lambda i: min(255, int(i * 1.05))),
                b.point(lambda i: int(i * 0.85)),
            ))
        elif any(k in p for k in ("cricket", "sports", "ipl")):
            out = ImageEnhance.Contrast(out).enhance(1.2)
            out = ImageEnhance.Color(out).enhance(1.3)
        else:
            out = ImageOps.solarize(out)

        out.save(output_path)


generator = GeneratorService()