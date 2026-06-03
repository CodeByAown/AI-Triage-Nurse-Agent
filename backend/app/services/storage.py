"""
Pluggable document storage (V4 Phase 2).

Default backend is the local filesystem (works out of the box with no cloud
config). The interface is deliberately small so a Supabase Storage / S3 backend
can be dropped in later by implementing the same three operations and switching
on ``settings.s3_bucket_name``.

Files are stored under ``<upload_dir>/<patient_id>/<uuid>_<safe_filename>`` so
originals are kept per-patient and never overwrite each other.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(filename: str) -> str:
    base = os.path.basename(filename or "file")
    cleaned = _SAFE.sub("_", base).strip("._") or "file"
    return cleaned[:120]


class LocalStorage:
    backend = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def save(self, *, patient_id: uuid.UUID, filename: str, data: bytes) -> str:
        folder = self.root / str(patient_id)
        folder.mkdir(parents=True, exist_ok=True)
        key = f"{uuid.uuid4().hex}_{_safe_name(filename)}"
        path = folder / key
        path.write_bytes(data)
        # Store a path relative to root so the DB value is portable.
        return str(Path(str(patient_id)) / key)

    def read(self, storage_path: str) -> bytes:
        return (self.root / storage_path).read_bytes()

    def delete(self, storage_path: str) -> None:
        try:
            (self.root / storage_path).unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            logger.error("storage_delete_failed", error=str(e), path=storage_path)

    def abs_path(self, storage_path: str) -> str:
        return str(self.root / storage_path)


def get_storage() -> LocalStorage:
    """Return the active storage backend. Local for now; S3/Supabase later."""
    return LocalStorage(settings.upload_dir)
