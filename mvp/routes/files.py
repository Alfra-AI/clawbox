"""File management routes."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mvp.auth import get_current_token
from mvp.database import get_db
from mvp.models import File as FileModel, Token
from mvp.storage import get_storage_backend
from mvp.embeddings import generate_and_store_embeddings

router = APIRouter(prefix="/files", tags=["files"])


class FileResponse(BaseModel):
    """Response model for file metadata."""

    id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Response model for file listing."""

    files: List[FileResponse]
    total: int


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

    # Create file record
    file_record = FileModel(
        token_id=token.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        storage_path="",  # Will be updated after save
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

    # Generate embeddings for searchable file types
    searchable_types = ["text/", "application/json", "application/xml", "application/pdf"]
    if any(file_record.content_type.startswith(t) for t in searchable_types):
        try:
            await generate_and_store_embeddings(
                db, file_record, content, file_record.content_type
            )
        except Exception:
            # Don't fail upload if embedding generation fails
            pass

    return FileResponse(
        id=str(file_record.id),
        filename=file_record.filename,
        content_type=file_record.content_type,
        size_bytes=file_record.size_bytes,
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
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in files
        ],
        total=len(files),
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
