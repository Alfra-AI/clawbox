"""Storage backend abstraction for file storage."""

import os
import shutil
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from src.config import settings


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


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(
        self,
        bucket_name: str | None = None,
        region: str | None = None,
    ):
        self.bucket_name = bucket_name or settings.s3_bucket_name
        self.region = region or settings.aws_region

        client_kwargs = {
            "region_name": self.region,
            "aws_access_key_id": settings.aws_access_key_id or None,
            "aws_secret_access_key": settings.aws_secret_access_key or None,
        }
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        self.s3_client = boto3.client("s3", **client_kwargs)

    def _get_s3_key(self, token_id: UUID, file_id: UUID, filename: str) -> str:
        """Generate S3 key for a file."""
        return f"{token_id}/{file_id}_{filename}"

    async def save(self, token_id: UUID, file_id: UUID, file_data: BinaryIO, filename: str) -> str:
        """Save a file to S3."""
        s3_key = self._get_s3_key(token_id, file_id, filename)

        self.s3_client.upload_fileobj(
            file_data,
            self.bucket_name,
            s3_key,
        )

        return s3_key

    async def load(self, storage_path: str) -> bytes:
        """Load a file from S3."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_path,
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {storage_path}")
            raise

    async def delete(self, storage_path: str) -> None:
        """Delete a file from S3."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_path,
            )
        except ClientError:
            pass  # Ignore errors on delete

    async def exists(self, storage_path: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_path,
            )
            return True
        except ClientError:
            return False


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    if settings.storage_backend == "local":
        return LocalStorageBackend()
    elif settings.storage_backend == "s3":
        return S3StorageBackend()
    else:
        raise ValueError(f"Unknown storage backend: {settings.storage_backend}")
