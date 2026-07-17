#!/usr/bin/env python3
"""
seed.py — Populates the JSON DB with sample folders and image stubs.
Run: python seed.py

This does NOT upload to Cloudinary (stubs are status=done with placeholder URLs).
"""

import json
import os
import uuid
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "db/database.json")

SAMPLE_DATA = {
    "folders": {},
    "images": {},
}

folders = [
    {"name": "Nature",      "description": "Landscapes and wildlife"},
    {"name": "Architecture","description": "Buildings and cityscapes"},
    {"name": "Portraits",   "description": "AI-generated portraits"},
]

PLACEHOLDER = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400"
PROMPTS = [
    "A breathtaking mountain landscape at golden hour, dramatic lighting, photorealistic",
    "Ancient stone temple surrounded by jungle vines, mystical atmosphere, ultra-detailed",
    "Portrait of a wise elder, soft natural light, Rembrandt lighting, oil painting style",
    "Futuristic cityscape at night with neon reflections on wet streets, cyberpunk aesthetic",
    "Serene Japanese zen garden with cherry blossoms, misty morning, watercolor style",
]

now = datetime.utcnow().isoformat()
folder_ids = []

for i, f in enumerate(folders):
    fid = str(uuid.uuid4())
    folder_ids.append(fid)
    SAMPLE_DATA["folders"][fid] = {
        "id": fid,
        "name": f["name"],
        "description": f["description"],
        "created_at": now,
    }

for i, fid in enumerate(folder_ids):
    for j in range(2):
        iid = str(uuid.uuid4())
        prompt_idx = (i * 2 + j) % len(PROMPTS)
        SAMPLE_DATA["images"][iid] = {
            "id": iid,
            "folder_id": fid,
            "filename": f"sample_{j+1}.jpg",
            "cloudinary_url": PLACEHOLDER,
            "public_id": f"sample/{iid}",
            "prompt": PROMPTS[prompt_idx],     # stored in DB, never exposed by list APIs
            "metadata": {"width": 800, "height": 600, "format": "jpg", "bytes": 102400},
            "status": "done",
            "created_at": now,
            "updated_at": now,
            "error": None,
        }

os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
with open(DB_PATH, "w") as f:
    json.dump(SAMPLE_DATA, f, indent=2)

print(f"✅ Seeded {len(SAMPLE_DATA['folders'])} folders and {len(SAMPLE_DATA['images'])} images → {DB_PATH}")
print("\nFolder IDs:")
for fid, fdata in SAMPLE_DATA["folders"].items():
    count = sum(1 for img in SAMPLE_DATA["images"].values() if img["folder_id"] == fid)
    print(f"  {fdata['name']}: {fid}  ({count} images)")