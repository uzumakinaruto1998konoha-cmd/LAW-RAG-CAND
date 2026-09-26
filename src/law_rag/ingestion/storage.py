"""Quarantine and immutable content-addressed filesystem blob storage."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path

from .errors import StorageError

LOGGER = logging.getLogger(__name__)


class FileBlobStore:
    """Store files under hash-derived keys; original names never form paths."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.quarantine = self.root / "quarantine"
        self.blobs = self.root / "blobs"
        try:
            self.quarantine.mkdir(parents=True, exist_ok=True)
            self.blobs.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError("Blob storage could not be initialized") from exc

    def put(self, content: bytes, sha256: str) -> str:
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != sha256:
            raise StorageError("Content hash did not match validated upload")
        target = self.blobs / sha256[:2] / sha256
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha256:
                    raise StorageError("Existing content-addressed blob failed integrity check")
                return sha256
            fd, temp_name = tempfile.mkstemp(prefix="upload-", dir=self.quarantine)
            temp_path = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(temp_path, target)
                except FileExistsError:
                    if hashlib.sha256(target.read_bytes()).hexdigest() != sha256:
                        raise StorageError("Concurrent blob failed integrity check")
                return sha256
            finally:
                temp_path.unlink(missing_ok=True)
        except OSError as exc:
            LOGGER.exception("Blob storage operation failed sha256=%s", sha256)
            raise StorageError("Blob storage operation failed") from exc

    def path_for(self, storage_key: str) -> Path:
        if len(storage_key) != 64 or any(ch not in "0123456789abcdef" for ch in storage_key):
            raise StorageError("Invalid storage key")
        return self.blobs / storage_key[:2] / storage_key
