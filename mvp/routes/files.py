"""File management routes."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from mvp.auth import get_current_token
from mvp.config import settings
from mvp.database import get_db
from mvp.models import File as FileModel, FileEmbedding, Token
from mvp.storage import get_storage_backend
from mvp.embeddings import generate_and_store_embeddings

router = APIRouter(prefix="/files", tags=["files"])

EMBEDDABLE_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
)


def is_embeddable_content_type(content_type: str) -> bool:
    """Return True when the file type should be embedded automatically."""
    return any(content_type.startswith(prefix) for prefix in EMBEDDABLE_CONTENT_TYPES)


class FileResponse(BaseModel):
    """Response model for file metadata."""

    id: str
    filename: str
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


class EmbedFileResult(BaseModel):
    requested_id: str
    id: Optional[str] = None
    filename: Optional[str] = None
    embedding_status: str
    error: Optional[str] = None


class BatchEmbedResponse(BaseModel):
    processed: int
    succeeded: int
    failed: int
    results: List[EmbedFileResult]


class BatchEmbedRequest(BaseModel):
    file_ids: Optional[List[UUID]] = None
    failed_only: bool = False

    @model_validator(mode="after")
    def validate_selector(self) -> "BatchEmbedRequest":
        has_file_ids = self.file_ids is not None and len(self.file_ids) > 0
        if has_file_ids == self.failed_only:
            raise ValueError("Provide either file_ids or failed_only=true")
        return self


async def _reembed_file(
    db: Session,
    file_record: FileModel,
    content: bytes,
) -> EmbedFileResult:
    """Generate embeddings for one file and return the batch result."""
    db.query(FileEmbedding).filter(FileEmbedding.file_id == file_record.id).delete()
    file_record.embedding_status = "pending"
    db.commit()

    try:
        success = await generate_and_store_embeddings(
            db, file_record, content, file_record.content_type
        )
        file_record.embedding_status = "completed" if success else "failed"
        error = None if success else "embedding_generation_failed"
    except Exception:
        db.rollback()
        file_record.embedding_status = "failed"
        error = "embedding_generation_failed"

    db.add(file_record)
    db.commit()

    return EmbedFileResult(
        requested_id=str(file_record.id),
        id=str(file_record.id),
        filename=file_record.filename,
        embedding_status=file_record.embedding_status,
        error=error,
    )


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Upload a file.

    The file will be stored and indexed for semantic search.
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
    embedding_status = "pending" if is_embeddable_content_type(content_type) else "not_applicable"

    # Create file record
    file_record = FileModel(
        token_id=token.id,
        filename=file.filename or "unnamed",
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

    db.commit()
    db.refresh(file_record)

    # Generate embeddings for embeddable file types
    if file_record.embedding_status == "pending":
        try:
            success = await generate_and_store_embeddings(
                db, file_record, content, file_record.content_type
            )
            file_record.embedding_status = "completed" if success else "failed"
        except Exception:
            db.rollback()
            file_record.embedding_status = "failed"
        db.add(file_record)
        db.commit()
        db.refresh(file_record)

    return FileResponse(
        id=str(file_record.id),
        filename=file_record.filename,
        content_type=file_record.content_type,
        size_bytes=file_record.size_bytes,
        embedding_status=file_record.embedding_status,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
    )


@router.get("", response_model=FileListResponse)
def list_files(
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> FileListResponse:
    """List all files for the current token."""
    files = db.query(FileModel).filter(FileModel.token_id == token.id).all()

    return FileListResponse(
        files=[
            FileResponse(
                id=str(f.id),
                filename=f.filename,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
                embedding_status=f.embedding_status,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in files
        ],
        total=len(files),
    )


@router.post("/embed", response_model=BatchEmbedResponse)
async def batch_embed_files(
    request: BatchEmbedRequest,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> BatchEmbedResponse:
    """Embed selected files or retry all files that previously failed."""
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embeddings not available. OpenAI API key not configured.",
        )

    storage = get_storage_backend()
    results: List[EmbedFileResult] = []
    succeeded = 0
    failed = 0

    if request.failed_only:
        file_records = (
            db.query(FileModel)
            .filter(FileModel.token_id == token.id, FileModel.embedding_status == "failed")
            .all()
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
            failed += 1
            results.append(
                EmbedFileResult(
                    requested_id=missing_id,
                    embedding_status="failed",
                    error="file_not_found",
                )
            )

        file_records = [files_by_id[requested_id] for requested_id in requested_ids if requested_id in files_by_id]

    if not file_records and not results:
        return BatchEmbedResponse(processed=0, succeeded=0, failed=0, results=[])

    for file_record in file_records:
        try:
            content = await storage.load(file_record.storage_path)
        except FileNotFoundError:
            failed += 1
            file_record.embedding_status = "failed"
            db.add(file_record)
            db.commit()
            results.append(
                EmbedFileResult(
                    requested_id=str(file_record.id),
                    id=str(file_record.id),
                    filename=file_record.filename,
                    embedding_status="failed",
                    error="file_not_found_in_storage",
                )
            )
            continue

        result = await _reembed_file(db, file_record, content)
        if result.embedding_status == "completed":
            succeeded += 1
        else:
            failed += 1
        results.append(result)

    return BatchEmbedResponse(
        processed=len(results),
        succeeded=succeeded,
        failed=failed,
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

    # Delete from database (cascades to embeddings)
    db.delete(file_record)
    db.commit()
