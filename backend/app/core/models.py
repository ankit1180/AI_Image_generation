from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


# ─── DB-level models (full, includes prompt) ──────────────────────────────────

class ImageRecord(BaseModel):
    """Internal record stored in JSON DB — prompt is present here."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    folder_id: str
    filename: str
    cloudinary_url: str = ""
    public_id: str = ""
    prompt: str = ""                  # NEVER sent to listing APIs
    metadata: Dict[str, Any] = {}
    status: str = "pending"           # pending | processing | done | error
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None


class FolderRecord(BaseModel):
    """Internal folder record."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ─── API-level response models (prompt is stripped) ───────────────────────────

class ImageSummary(BaseModel):
    """Returned in folder image listings — NO prompt."""
    id: str
    filename: str
    cloudinary_url: str
    public_id: str
    status: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str


class ImageDetail(BaseModel):
    """Returned from single-image fetch — NO prompt."""
    id: str
    folder_id: str
    filename: str
    cloudinary_url: str
    public_id: str
    status: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    error: Optional[str] = None


class FolderSummary(BaseModel):
    """Returned in folder listings."""
    id: str
    name: str
    description: str
    created_at: str
    image_count: int = 0


class PromptResponse(BaseModel):
    """Returned ONLY from secure prompt endpoint."""
    image_id: str
    prompt: str


# ─── Request models ────────────────────────────────────────────────────────────

class UploadRequest(BaseModel):
    folder_id: str
    filename: str
    prompt: str
    metadata: Dict[str, Any] = {}


class CreateFolderRequest(BaseModel):
    name: str
    description: str = ""


# ─── Task / async response models ─────────────────────────────────────────────

class TaskResponse(BaseModel):
    task_id: str
    image_id: str
    status: str = "queued"
    message: str = ""