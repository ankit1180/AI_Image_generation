"""
Sync img_prompt.json → img_prompt_cloudinary.json
===================================================
Uploads all preview images to Cloudinary and writes an extended
JSON file with cloudinary_url + public_id alongside the original URL.

Run once before starting the app:
    cd project/
    python backend/scripts/sync_cloudinary.py

After running, update backend/app/core/config.py:
    IMG_PROMPT_FILE: Path = BASE_DIR.parent / "img_prompt_cloudinary.json"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------
# Make backend app imports available
# ---------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]   # project/
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import cloudinary
import cloudinary.uploader

from app.core.config import settings


# ---------------------------------------------------------
# Cloudinary setup
# ---------------------------------------------------------
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


# ---------------------------------------------------------
# File paths
# ---------------------------------------------------------
INPUT_FILE  = ROOT_DIR / "img_prompt.json"
OUTPUT_FILE = ROOT_DIR / "img_prompt_cloudinary.json"


# ---------------------------------------------------------
# JSON loader (handles the { {…},{…} } non-standard wrapper)
# ---------------------------------------------------------
def _load_json(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    # Normalise Windows line endings
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    # img_prompt.json wraps items as { {…}, {…} } instead of [{…},{…}]
    if raw.startswith("{") and not raw.startswith('{"'):
        raw = "[" + raw.lstrip("{").rstrip("}") + "]"
    return json.loads(raw)


# ---------------------------------------------------------
# Upload a single URL to Cloudinary
# ---------------------------------------------------------
def upload_url(image_url: str) -> tuple[str | None, str | None]:
    """
    Returns (cloudinary_secure_url, public_id) or (None, None) on failure.
    """
    try:
        result = cloudinary.uploader.upload(
            image_url,
            folder=settings.CLOUDINARY_FOLDER,
            overwrite=False,
            unique_filename=True,
            resource_type="image",
        )
        return result["secure_url"], result["public_id"]
    except Exception as exc:
        print(f"  [ERROR] {exc}")
        return None, None


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"{INPUT_FILE} not found")

    print(f"Loading {INPUT_FILE}…")
    folders = _load_json(INPUT_FILE)
    print(f"Found {len(folders)} folders.")

    total = uploaded = 0
    output_folders = []

    for folder in folders:
        folder_name: str = folder.get("folder_name", "Unnamed")
        images: list[dict] = folder.get("images", [])
        print(f"\nFolder: {folder_name} ({len(images)} images)")

        new_images = []
        for img in images:
            total += 1
            original_url: str = img.get("image_url", "").strip()
            prompt: str = img.get("prompt", "")

            if not original_url:
                continue

            print(f"  Uploading: {original_url[:70]}…")
            cdurl, pub_id = upload_url(original_url)

            if cdurl:
                uploaded += 1
                print(f"  ✓ {cdurl[:60]}…")
            else:
                print(f"  ✗ kept original URL")

            new_images.append({
                "original_url": original_url,       # preserved – never replaced
                "cloudinary_url": cdurl,             # null if upload failed
                "public_id": pub_id,
                "uploaded": cdurl is not None,
                "prompt": prompt,                    # stays in file, never sent to frontend
            })

        output_folders.append({"folder_name": folder_name, "images": new_images})

    OUTPUT_FILE.write_text(
        json.dumps(output_folders, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 50)
    print(f"Total images : {total}")
    print(f"Uploaded     : {uploaded}")
    print(f"Failed       : {total - uploaded}")
    print(f"Output file  : {OUTPUT_FILE}")
    print("=" * 50)
    print("\nNext step: in backend/app/core/config.py set:")
    print('  IMG_PROMPT_FILE: Path = BASE_DIR.parent / "img_prompt_cloudinary.json"')


if __name__ == "__main__":
    main()