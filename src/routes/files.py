"""File management routes."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from src.auth import get_current_token
from src.config import settings
from src.database import get_db
from src.embedding_jobs import (
    FILE_STATUS_FAILED,
    FILE_STATUS_NOT_APPLICABLE,
    FILE_STATUS_PROCESSING,
    FILE_STATUS_QUEUED,
    enqueue_embedding_job,
    get_embeddable_files_for_selector,
)
from src.models import File as FileModel, SharedLink, Token
from src.storage import get_storage_backend

router = APIRouter(prefix="/files", tags=["files"])

# Map file extensions to correct MIME types (fallback when client sends application/octet-stream)
EXTENSION_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".md": "text/markdown",
    ".txt": "text/plain",
}

EMBEDDABLE_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "video/mp4",
    "video/quicktime",  # .mov
    "audio/mpeg",  # .mp3
    "audio/wav",
    "audio/x-wav",
)


def is_embeddable_content_type(content_type: str) -> bool:
    """Return True when the file type should be embedded automatically."""
    return any(content_type.startswith(prefix) for prefix in EMBEDDABLE_CONTENT_TYPES)


class FileResponse(BaseModel):
    """Response model for file metadata."""

    id: str
    filename: str
    folder: str
    content_type: str
    size_bytes: int
    embedding_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Response model for file listing."""

    files: List[FileResponse]
    total: int
    storage_used_bytes: int = 0
    storage_limit_bytes: int = 0


class EmbedFileResult(BaseModel):
    requested_id: str
    id: Optional[str] = None
    filename: Optional[str] = None
    embedding_status: str
    error: Optional[str] = None


class BatchEmbedResponse(BaseModel):
    processed: int
    queued: int
    skipped: int
    results: List[EmbedFileResult]


class BatchEmbedRequest(BaseModel):
    file_ids: Optional[List[UUID]] = None
    failed_only: bool = False
    pending_only: bool = False

    @model_validator(mode="after")
    def validate_selector(self) -> "BatchEmbedRequest":
        has_file_ids = self.file_ids is not None and len(self.file_ids) > 0
        selectors = sum([has_file_ids, self.failed_only, self.pending_only])
        if selectors != 1:
            raise ValueError("Provide exactly one of: file_ids, failed_only=true, or pending_only=true")
        return self



def _parse_path(path: str, default_filename: str) -> tuple[str, str]:
    """Parse a virtual path into (folder, filename).

    Examples:
        "/reports/q1.pdf" → ("/reports/", "q1.pdf")
        "/docs/"          → ("/docs/", default_filename)
        "notes.txt"       → ("/", "notes.txt")
        ""                → ("/", default_filename)
    """
    path = path.strip()
    if not path:
        return "/", default_filename

    # Normalize: ensure leading slash
    if not path.startswith("/"):
        path = "/" + path

    if path.endswith("/"):
        # Path is a folder only
        return path, default_filename

    # Split into folder + filename
    last_slash = path.rfind("/")
    folder = path[: last_slash + 1] or "/"
    filename = path[last_slash + 1 :] or default_filename
    return folder, filename


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    path: Optional[str] = Form(None),
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Upload a file.

    The file will be stored and indexed for semantic search.
    Optionally provide a `path` (e.g., `/reports/q1.pdf`) to organize files into folders.
    """
    # Read file content to get size
    content = await file.read()
    size_bytes = len(content)

    # Check storage quota
    if not token.has_storage_available(size_bytes):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Storage quota exceeded. Available: {token.storage_limit_bytes - token.storage_used_bytes} bytes",
        )

    content_type = file.content_type or "application/octet-stream"
    # Fix content type from extension if client sent a generic type
    if content_type in ("application/octet-stream", ""):
        import os
        ext = os.path.splitext(file.filename or "")[-1].lower()
        content_type = EXTENSION_CONTENT_TYPES.get(ext, content_type)
    embedding_status = FILE_STATUS_QUEUED if is_embeddable_content_type(content_type) else FILE_STATUS_NOT_APPLICABLE

    # Parse virtual path
    default_filename = file.filename or "unnamed"
    folder, filename = _parse_path(path or "", default_filename)

    # Create file record
    file_record = FileModel(
        token_id=token.id,
        filename=filename,
        folder=folder,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_path="",  # Will be updated after save
        embedding_status=embedding_status,
    )
    db.add(file_record)
    db.flush()  # Get the file ID

    # Save to storage
    storage = get_storage_backend()
    from io import BytesIO
    storage_path = await storage.save(
        token_id=token.id,
        file_id=file_record.id,
        file_data=BytesIO(content),
        filename=file_record.filename,
    )
    file_record.storage_path = storage_path

    # Update token storage usage
    token.storage_used_bytes += size_bytes

    if file_record.embedding_status == FILE_STATUS_QUEUED:
        enqueue_embedding_job(db, file_record, requested_by="upload")

    db.commit()
    db.refresh(file_record)

    return FileResponse(
        id=str(file_record.id),
        filename=file_record.filename,
        folder=file_record.folder,
        content_type=file_record.content_type,
        size_bytes=file_record.size_bytes,
        embedding_status=file_record.embedding_status,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
    )


@router.get("", response_model=FileListResponse)
def list_files(
    folder: Optional[str] = None,
    recursive: bool = False,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> FileListResponse:
    """List files for the current token, optionally filtered by folder."""
    query = db.query(FileModel).filter(FileModel.token_id == token.id)

    if folder:
        # Normalize folder path
        if not folder.startswith("/"):
            folder = "/" + folder
        if not folder.endswith("/"):
            folder = folder + "/"
        if recursive:
            query = query.filter(FileModel.folder.startswith(folder))
        else:
            query = query.filter(FileModel.folder == folder)

    files = query.all()

    return FileListResponse(
        files=[
            FileResponse(
                id=str(f.id),
                filename=f.filename,
                folder=f.folder,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
                embedding_status=f.embedding_status,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in files
        ],
        total=len(files),
        storage_used_bytes=token.storage_used_bytes,
        storage_limit_bytes=token.storage_limit_bytes,
    )


@router.post("/embed", response_model=BatchEmbedResponse)
async def batch_embed_files(
    request: BatchEmbedRequest,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> BatchEmbedResponse:
    """Queue selected files or retry all files that previously failed."""
    results: List[EmbedFileResult] = []
    queued = 0
    skipped = 0

    if request.failed_only or request.pending_only:
        file_records = get_embeddable_files_for_selector(
            db,
            token.id,
            failed_only=request.failed_only,
            pending_only=request.pending_only,
        )
        requested_ids = list(dict.fromkeys(str(file_record.id) for file_record in file_records))
    else:
        requested_ids = list(dict.fromkeys(str(file_id) for file_id in request.file_ids or []))
        file_records = (
            db.query(FileModel)
            .filter(FileModel.token_id == token.id, FileModel.id.in_(request.file_ids or []))
            .all()
        )
        files_by_id = {str(file_record.id): file_record for file_record in file_records}
        missing_ids = [requested_id for requested_id in requested_ids if requested_id not in files_by_id]

        if len(requested_ids) == 1 and missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        for missing_id in missing_ids:
            skipped += 1
            results.append(
                EmbedFileResult(
                    requested_id=missing_id,
                    embedding_status=FILE_STATUS_FAILED,
                    error="file_not_found",
                )
            )

        file_records = [files_by_id[requested_id] for requested_id in requested_ids if requested_id in files_by_id]

    if not file_records and not results:
        return BatchEmbedResponse(processed=0, queued=0, skipped=0, results=[])

    for file_record in file_records:
        if file_record.embedding_status == FILE_STATUS_NOT_APPLICABLE:
            skipped += 1
            results.append(
                EmbedFileResult(
                    requested_id=str(file_record.id),
                    id=str(file_record.id),
                    filename=file_record.filename,
                    embedding_status=FILE_STATUS_NOT_APPLICABLE,
                    error="unsupported_content_type",
                )
            )
            continue

        job, created = enqueue_embedding_job(db, file_record, requested_by="api")
        if created:
            queued += 1
        else:
            skipped += 1

        public_status = file_record.embedding_status
        if public_status not in (FILE_STATUS_QUEUED, FILE_STATUS_PROCESSING):
            public_status = FILE_STATUS_PROCESSING if job and job.status in ("leased", "running") else FILE_STATUS_QUEUED
        results.append(
            EmbedFileResult(
                requested_id=str(file_record.id),
                id=str(file_record.id),
                filename=file_record.filename,
                embedding_status=public_status,
                error=None if created else "already_queued",
            )
        )

    db.commit()

    return BatchEmbedResponse(
        processed=len(results),
        queued=queued,
        skipped=skipped,
        results=results,
    )


@router.get("/{file_id}")
async def download_file(
    file_id: UUID,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> Response:
    """Download a file by ID."""
    file_record = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.token_id == token.id)
        .first()
    )

    if file_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    storage = get_storage_backend()
    try:
        content = await storage.load(file_record.storage_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )

    return Response(
        content=content,
        media_type=file_record.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.filename}"',
        },
    )


class MoveFileRequest(BaseModel):
    """Request to move/rename a file."""
    path: str


@router.patch("/{file_id}", response_model=FileResponse)
def move_file(
    file_id: UUID,
    request: MoveFileRequest,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Move or rename a file by providing a new path."""
    file_record = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.token_id == token.id)
        .first()
    )
    if file_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    folder, filename = _parse_path(request.path, file_record.filename)
    file_record.folder = folder
    file_record.filename = filename
    db.commit()
    db.refresh(file_record)

    return FileResponse(
        id=str(file_record.id),
        filename=file_record.filename,
        folder=file_record.folder,
        content_type=file_record.content_type,
        size_bytes=file_record.size_bytes,
        embedding_status=file_record.embedding_status,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> None:
    """Delete a file by ID."""
    file_record = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.token_id == token.id)
        .first()
    )

    if file_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Delete from storage
    storage = get_storage_backend()
    await storage.delete(file_record.storage_path)

    # Update token storage usage
    token.storage_used_bytes -= file_record.size_bytes

    # Delete from database (cascades to embeddings + shared links)
    db.delete(file_record)
    db.commit()


# --- File Sharing ---

import secrets


class ShareRequest(BaseModel):
    """Request to create a shared link."""
    expires_in: Optional[int] = None  # seconds, None = no expiry
    max_downloads: Optional[int] = None  # None = unlimited


class ShareResponse(BaseModel):
    """Response with shared link details."""
    code: str
    url: str
    expires_at: Optional[datetime] = None
    max_downloads: Optional[int] = None


class ShareListResponse(BaseModel):
    """Response listing shared links for a file."""
    links: list[ShareResponse]


@router.post("/{file_id}/share", response_model=ShareResponse, status_code=status.HTTP_201_CREATED)
def create_shared_link(
    file_id: UUID,
    request: ShareRequest = ShareRequest(),
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ShareResponse:
    """Create a shared link for a file."""
    file_record = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.token_id == token.id)
        .first()
    )
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    code = secrets.token_urlsafe(6)[:8]  # 8-char URL-safe code
    expires_at = None
    if request.expires_in:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(seconds=request.expires_in)

    link = SharedLink(
        file_id=file_record.id,
        code=code,
        expires_at=expires_at,
        max_downloads=request.max_downloads,
    )
    db.add(link)
    db.commit()

    return ShareResponse(
        code=code,
        url=f"{settings.app_url}/s/{code}",
        expires_at=expires_at,
        max_downloads=request.max_downloads,
    )


@router.get("/{file_id}/shares", response_model=ShareListResponse)
def list_shared_links(
    file_id: UUID,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ShareListResponse:
    """List shared links for a file."""
    file_record = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.token_id == token.id)
        .first()
    )
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    links = db.query(SharedLink).filter(SharedLink.file_id == file_id).all()

    return ShareListResponse(
        links=[
            ShareResponse(
                code=link.code,
                url=f"{settings.app_url}/s/{link.code}",
                expires_at=link.expires_at,
                max_downloads=link.max_downloads,
            )
            for link in links
        ]
    )


@router.delete("/{file_id}/share/{code}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_shared_link(
    file_id: UUID,
    code: str,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> None:
    """Revoke a shared link."""
    file_record = (
        db.query(FileModel)
        .filter(FileModel.id == file_id, FileModel.token_id == token.id)
        .first()
    )
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    link = (
        db.query(SharedLink)
        .filter(SharedLink.file_id == file_id, SharedLink.code == code)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.commit()
