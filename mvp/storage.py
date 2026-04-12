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

    def generate_presigned_upload_url(self, token_id: UUID, file_id: UUID, filename: str, expires_in: int = 3600) -> dict | None:
        """Generate a presigned URL for direct upload. Returns None if not supported."""
        return None

    def generate_presigned_download_url(self, storage_path: str, filename: str, expires_in: int = 3600) -> str | None:
        """Generate a presigned URL for direct download. Returns None if not supported."""
        return None

    def generate_presigned_multipart_upload(self, token_id: UUID, file_id: UUID, filename: str, num_parts: int, expires_in: int = 3600) -> dict | None:
        """Initiate multipart upload and return presigned URLs for each part. Returns None if not supported."""
        return None

    def complete_multipart_upload(self, storage_path: str, upload_id: str, parts: list) -> bool:
        """Complete a multipart upload with ETags. Returns True on success."""
        return False

    def abort_multipart_upload(self, storage_path: str, upload_id: str) -> None:
        """Abort an in-progress multipart upload."""
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

    def generate_presigned_upload_url(self, token_id: UUID, file_id: UUID, filename: str, expires_in: int = 3600) -> dict | None:
        """Generate a presigned URL for direct upload to S3."""
        s3_key = self._get_s3_key(token_id, file_id, filename)
        url = self.s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket_name, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return {"upload_url": url, "storage_path": s3_key}

    def generate_presigned_download_url(self, storage_path: str, filename: str, expires_in: int = 3600) -> str | None:
        """Generate a presigned URL for direct download from S3."""
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": storage_path,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=expires_in,
        )

    def generate_presigned_multipart_upload(self, token_id: UUID, file_id: UUID, filename: str, num_parts: int, expires_in: int = 3600) -> dict | None:
        """Initiate S3 multipart upload and return presigned URLs for each part."""
        s3_key = self._get_s3_key(token_id, file_id, filename)

        # Create multipart upload
        response = self.s3_client.create_multipart_upload(
            Bucket=self.bucket_name,
            Key=s3_key,
        )
        upload_id = response["UploadId"]

        # Generate presigned URL for each part
        part_urls = []
        for i in range(1, num_parts + 1):
            url = self.s3_client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,
                    "PartNumber": i,
                    "UploadId": upload_id,
                },
                ExpiresIn=expires_in,
            )
            part_urls.append({"part_number": i, "upload_url": url})

        return {
            "upload_id": upload_id,
            "storage_path": s3_key,
            "part_urls": part_urls,
        }

    def complete_multipart_upload(self, storage_path: str, upload_id: str, parts: list) -> bool:
        """Complete an S3 multipart upload with ETags."""
        self.s3_client.complete_multipart_upload(
            Bucket=self.bucket_name,
            Key=storage_path,
            UploadId=upload_id,
            MultipartUpload={
                "Parts": [
                    {"PartNumber": p["part_number"], "ETag": p["etag"]}
                    for p in sorted(parts, key=lambda x: x["part_number"])
                ]
            },
        )
        return True

    def abort_multipart_upload(self, storage_path: str, upload_id: str) -> None:
        """Abort an S3 multipart upload."""
        try:
            self.s3_client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=storage_path,
                UploadId=upload_id,
            )
        except ClientError:
            pass


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    if settings.storage_backend == "local":
        return LocalStorageBackend()
    elif settings.storage_backend == "s3":
        return S3StorageBackend()
    else:
        raise ValueError(f"Unknown storage backend: {settings.storage_backend}")
