"""
tests/test_api.py — Integration tests for all API endpoints.

Run: pytest tests/ -v
"""

import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

os.environ.setdefault("DB_PATH", "/tmp/test_db.json")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("PROMPT_API_SECRET", "test-secret")
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "test")
os.environ.setdefault("CLOUDINARY_API_KEY", "test")
os.environ.setdefault("CLOUDINARY_API_SECRET", "test")

from fastapi.testclient import TestClient

# Patch Redis before import
with patch("redis.from_url") as mock_redis:
    mock_redis.return_value = MagicMock(
        get=lambda k: None, setex=lambda *a: None,
        delete=lambda k: None, keys=lambda p: [], ping=lambda: True,
    )
    from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Start each test with a fresh DB."""
    path = os.environ["DB_PATH"]
    with open(path, "w") as f:
        json.dump({"folders": {}, "images": {}}, f)
    yield
    if os.path.exists(path):
        os.remove(path)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/v1/health/")
    assert r.status_code == 200
    assert "status" in r.json()


# ── Folders ───────────────────────────────────────────────────────────────────

def test_list_folders_empty():
    r = client.get("/api/v1/folders/")
    assert r.status_code == 200
    assert r.json() == []


def test_create_folder():
    r = client.post("/api/v1/folders/", json={"name": "Test", "description": "desc"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Test"
    assert "id" in data
    assert "prompt" not in data


def test_list_folders_after_create():
    client.post("/api/v1/folders/", json={"name": "A"})
    client.post("/api/v1/folders/", json={"name": "B"})
    r = client.get("/api/v1/folders/")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_folder_not_found():
    r = client.get("/api/v1/folders/nonexistent")
    assert r.status_code == 404


def test_delete_folder():
    cf = client.post("/api/v1/folders/", json={"name": "Del"}).json()
    r = client.delete(f"/api/v1/folders/{cf['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/folders/{cf['id']}")
    assert r2.status_code == 404


# ── Images ────────────────────────────────────────────────────────────────────

def _create_folder_and_image():
    folder = client.post("/api/v1/folders/", json={"name": "ImgTest"}).json()
    # Inject image directly into DB
    import db.json_db as db
    import uuid
    from datetime import datetime
    img = {
        "id": str(uuid.uuid4()),
        "folder_id": folder["id"],
        "filename": "test.jpg",
        "cloudinary_url": "https://res.cloudinary.com/test/image/upload/test.jpg",
        "public_id": "test/abc",
        "prompt": "A secret AI prompt",
        "metadata": {"width": 100, "height": 100},
        "status": "done",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "error": None,
    }
    db.create_image(img)
    return folder, img


def test_list_images_no_prompt():
    folder, img = _create_folder_and_image()
    r = client.get(f"/api/v1/images/folder/{folder['id']}")
    assert r.status_code == 200
    images = r.json()
    assert len(images) == 1
    # CRITICAL: prompt must never appear
    assert "prompt" not in images[0]
    assert images[0]["filename"] == "test.jpg"


def test_get_image_detail_no_prompt():
    _, img = _create_folder_and_image()
    r = client.get(f"/api/v1/images/{img['id']}")
    assert r.status_code == 200
    detail = r.json()
    assert "prompt" not in detail
    assert detail["filename"] == "test.jpg"


def test_prompt_requires_secret():
    _, img = _create_folder_and_image()
    # No header → 422 (missing required header)
    r = client.get(f"/api/v1/images/{img['id']}/prompt")
    assert r.status_code == 422

    # Wrong secret → 401
    r2 = client.get(
        f"/api/v1/images/{img['id']}/prompt",
        headers={"X-Prompt-Secret": "wrong-secret"},
    )
    assert r2.status_code == 401


def test_prompt_with_correct_secret():
    _, img = _create_folder_and_image()
    r = client.get(
        f"/api/v1/images/{img['id']}/prompt",
        headers={"X-Prompt-Secret": "test-secret"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["prompt"] == "A secret AI prompt"
    assert data["image_id"] == img["id"]


def test_image_not_found():
    r = client.get("/api/v1/images/nonexistent")
    assert r.status_code == 404


def test_delete_image():
    folder, img = _create_folder_and_image()
    r = client.delete(f"/api/v1/images/{img['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/images/{img['id']}")
    assert r2.status_code == 404


# ── Task polling ──────────────────────────────────────────────────────────────

def test_task_status_unknown():
    with patch("api.routes.tasks.AsyncResult") as mock_ar:
        mock_ar.return_value = MagicMock(state="PENDING", result=None, info=None)
        r = client.get("/api/v1/tasks/fake-task-id")
        assert r.status_code == 200
        assert r.json()["status"] == "PENDING"