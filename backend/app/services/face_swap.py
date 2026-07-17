"""
Face Swap Service
==================
Implements the actual engine behind "Generate Same Image" mode: a true
pixel-level face swap using insightface's inswapper model — NOT the SD1.5
diffusion pipeline used by generate_similar().

Why this needs to be a separate, non-diffusion pipeline
---------------------------------------------------------
"Generate Same Image" promises the sample's background, outfit, and pose
stay unchanged and ONLY the face changes. Running that through SD1.5
img2img — even at a low strength — still re-renders the *entire* image
through diffusion, so "unchanged" was never actually true; it just changed
less. inswapper instead:

  1. detects the face region on the sample image,
  2. detects the face on the user's uploaded photo,
  3. warps + pastes the user's face into that region only.

Every other pixel of the sample image is untouched. GFPGAN then runs a
light restoration pass (reused from generator.py) purely to clean up the
seam/blend, not to regenerate the scene.

This module reuses the SAME insightface FaceAnalysis singleton that
generator.py already loads for IP-Adapter-FaceID embeddings (via
`_get_face_analysis_app()`), so the buffalo_l detector model is only ever
loaded once per worker process regardless of which mode runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import settings

try:
    import cv2
    import numpy as np
    import insightface

    # Deferred/local-style dependency on generator.py: generator.py only
    # imports this module lazily, inside generate_same(), so by the time
    # that happens generator.py is already fully loaded and this import
    # is safe (no circular-import issue).
    from app.services.generator import (
        INSIGHTFACE_AVAILABLE,
        get_device,
        _get_face_analysis_app,
    )

    FACE_SWAP_AVAILABLE = INSIGHTFACE_AVAILABLE
except Exception as e:
    print(f"[FaceSwap] Unavailable: {e}")
    cv2 = None
    np = None
    insightface = None
    FACE_SWAP_AVAILABLE = False

    def get_device() -> str:
        return "cpu"

    def _get_face_analysis_app():
        return None


_inswapper_model = None  # lazy singleton
_inswapper_load_failed = False


# ---------------------------------------------------------------------------
# Weight download / loading
# ---------------------------------------------------------------------------


def _ensure_inswapper_weights() -> Path | None:
    """
    Download the inswapper_128.onnx weights on first use, caching them at
    settings.INSWAPPER_MODEL_PATH. Returns None (never raises) if the
    download fails, so callers can degrade gracefully instead of crashing
    the whole worker.
    """
    model_path = settings.INSWAPPER_MODEL_PATH
    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path

    try:
        import requests

        print(f"[FaceSwap] Downloading inswapper weights from {settings.INSWAPPER_MODEL_URL} ...")
        model_path.parent.mkdir(parents=True, exist_ok=True)

        # Stream to a .part file and rename on success, so a crash/kill
        # mid-download never leaves a corrupt file that looks "present".
        tmp_path = model_path.with_suffix(model_path.suffix + ".part")
        with requests.get(settings.INSWAPPER_MODEL_URL, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        tmp_path.rename(model_path)

        print(f"[FaceSwap] inswapper weights cached at {model_path}")
        return model_path
    except Exception as exc:
        print(f"[FaceSwap] Failed to download inswapper weights: {exc}")
        return None


def _get_inswapper_model():
    """Lazily load and cache the inswapper ONNX model."""
    global _inswapper_model, _inswapper_load_failed
    if _inswapper_model is not None:
        return _inswapper_model
    if not FACE_SWAP_AVAILABLE or _inswapper_load_failed:
        return None

    model_path = _ensure_inswapper_weights()
    if model_path is None:
        _inswapper_load_failed = True
        return None

    try:
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if get_device() == "cuda"
            else ["CPUExecutionProvider"]
        )
        _inswapper_model = insightface.model_zoo.get_model(str(model_path), providers=providers)
        print("[FaceSwap] inswapper model loaded.")
        return _inswapper_model
    except Exception as exc:
        print(f"[FaceSwap] Failed to load inswapper model: {exc}")
        _inswapper_load_failed = True
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _largest_face(faces: list) -> Any | None:
    """Pick the biggest detected face by bbox area (most likely the
    intended subject rather than someone in the background)."""
    if not faces:
        return None
    faces = sorted(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )
    return faces[0]


def swap_face(sample_image: "Image.Image", user_image: "Image.Image") -> "Image.Image | None":
    """
    Paste the largest face found in `user_image` onto the largest face
    found in `sample_image`. Every pixel of `sample_image` outside the
    swapped face region is left untouched.

    Returns None (never raises) if:
      - insightface/inswapper aren't available,
      - no face is detected in either image,
      - the swap itself errors out,
    so the caller (generator.generate_same) can surface a clear error
    instead of crashing with an opaque traceback.
    """
    if not FACE_SWAP_AVAILABLE:
        print("[FaceSwap] insightface unavailable — cannot swap faces.")
        return None

    app = _get_face_analysis_app()
    if app is None:
        print("[FaceSwap] Face analysis app unavailable — cannot swap faces.")
        return None

    swapper = _get_inswapper_model()
    if swapper is None:
        print("[FaceSwap] inswapper model unavailable — cannot swap faces.")
        return None

    try:
        sample_bgr = cv2.cvtColor(np.array(sample_image.convert("RGB")), cv2.COLOR_RGB2BGR)
        user_bgr = cv2.cvtColor(np.array(user_image.convert("RGB")), cv2.COLOR_RGB2BGR)

        target_face = _largest_face(app.get(sample_bgr))
        if target_face is None:
            print("[FaceSwap] No face detected in the sample/style image.")
            return None

        source_face = _largest_face(app.get(user_bgr))
        if source_face is None:
            print("[FaceSwap] No face detected in the uploaded photo.")
            return None

        result_bgr = swapper.get(sample_bgr, target_face, source_face, paste_back=True)
        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)
    except Exception as exc:
        print(f"[FaceSwap] Face swap failed: {exc}")
        return None