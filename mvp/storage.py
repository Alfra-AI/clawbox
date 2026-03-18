"""Storage backend abstraction for file storage."""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from mvp.config import settings


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(self, token_id: UUID, file_id: UUID, file_data: BinaryIO, filename: str) -> str:
        """Save a file and return the storage path."""
        pass

    @abstractmethod
    async def load(self, storage_path: str) -> bytes:
        """Load a file from storage."""
        pass

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def exists(self, storage_path: str) -> bool:
        """Check if a file exists in storage."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or settings.local_storage_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_token_dir(self, token_id: UUID) -> Path:
        """Get the directory for a token's files."""
        token_dir = self.base_path / str(token_id)
        token_dir.mkdir(parents=True, exist_ok=True)
        return token_dir

    async def save(self, token_id: UUID, file_id: UUID, file_data: BinaryIO, filename: str) -> str:
        """Save a file to local filesystem."""
        token_dir = self._get_token_dir(token_id)
        # Use file_id as the storage filename to avoid conflicts
        storage_filename = f"{file_id}_{filename}"
        file_path = token_dir / storage_filename

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file_data, f)

        # Return relative path from base
        return str(file_path.relative_to(self.base_path))

    async def load(self, storage_path: str) -> bytes:
        """Load a file from local filesystem."""
        file_path = self.base_path / storage_path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        with open(file_path, "rb") as f:
            return f.read()

    async def delete(self, storage_path: str) -> None:
        """Delete a file from local filesystem."""
        file_path = self.base_path / storage_path
        if file_path.exists():
            os.remove(file_path)

    async def exists(self, storage_path: str) -> bool:
        """Check if a file exists in local filesystem."""
        file_path = self.base_path / storage_path
        return file_path.exists()


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    if settings.storage_backend == "local":
        return LocalStorageBackend()
    else:
        raise ValueError(f"Unknown storage backend: {settings.storage_backend}")
