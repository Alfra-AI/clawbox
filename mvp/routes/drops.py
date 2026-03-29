"""Quick Drop routes — ephemeral file sharing with 4-digit PIN."""

import random
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mvp.database import get_db
from mvp.models import Drop
from mvp.storage import get_storage_backend

router = APIRouter(prefix="/drop", tags=["drop"])

MAX_DROP_SIZE = 100 * 1024 * 1024  # 100 MB
DEFAULT_EXPIRY_HOURS = 24


def _generate_code(db: Session) -> str:
    """Generate a unique 4-digit PIN code."""
    for _ in range(50):
        code = f"{random.randint(0, 9999):04d}"
        exists = db.query(Drop).filter(Drop.code == code).first()
        if not exists:
            return code
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Too many active drops, try again later",
    )


class DropResponse(BaseModel):
    code: str
    filename: str
    size_bytes: int
    expires_at: datetime
    max_downloads: int


class DropInfoResponse(BaseModel):
    filename: str
    size_bytes: int
    content_type: str
    downloads_remaining: int | None


@router.post("", response_model=DropResponse, status_code=status.HTTP_201_CREATED)
async def create_drop(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Drop a file — no auth needed. Returns a 4-digit PIN."""
    content = await file.read()
    size_bytes = len(content)

    if size_bytes > MAX_DROP_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Max drop size is {MAX_DROP_SIZE // (1024*1024)} MB",
        )

    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unnamed"
    code = _generate_code(db)
    expires_at = datetime.utcnow() + timedelta(hours=DEFAULT_EXPIRY_HOURS)

    # Store under drops/ prefix
    storage = get_storage_backend()
    from uuid import uuid4
    drop_id = uuid4()
    storage_path = await storage.save(
        token_id=uuid4(),  # use random UUID as namespace for drops
        file_id=drop_id,
        file_data=BytesIO(content),
        filename=filename,
    )

    drop = Drop(
        id=drop_id,
        code=code,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_path=storage_path,
        expires_at=expires_at,
    )
    db.add(drop)
    db.commit()

    return DropResponse(
        code=code,
        filename=filename,
        size_bytes=size_bytes,
        expires_at=expires_at,
        max_downloads=drop.max_downloads,
    )


@router.get("/{code}", response_model=DropInfoResponse)
def get_drop_info(code: str, db: Session = Depends(get_db)):
    """Get info about a drop before downloading."""
    drop = _get_valid_drop(code, db)

    remaining = None
    if drop.max_downloads:
        remaining = drop.max_downloads - drop.download_count

    return DropInfoResponse(
        filename=drop.filename,
        size_bytes=drop.size_bytes,
        content_type=drop.content_type,
        downloads_remaining=remaining,
    )


@router.get("/{code}/download")
async def download_drop(code: str, db: Session = Depends(get_db)):
    """Download a dropped file. Increments download count."""
    drop = _get_valid_drop(code, db)

    storage = get_storage_backend()
    try:
        content = await storage.load(drop.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in storage")

    drop.download_count += 1
    # Auto-delete after max downloads reached
    if drop.max_downloads and drop.download_count >= drop.max_downloads:
        await storage.delete(drop.storage_path)
        db.delete(drop)
    db.commit()

    return Response(
        content=content,
        media_type=drop.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{drop.filename}"',
        },
    )


def _get_valid_drop(code: str, db: Session) -> Drop:
    """Look up a drop by code, checking expiry and download limits."""
    drop = db.query(Drop).filter(Drop.code == code).first()
    if drop is None:
        raise HTTPException(status_code=404, detail="Drop not found")

    if datetime.utcnow() > drop.expires_at:
        db.delete(drop)
        db.commit()
        raise HTTPException(status_code=410, detail="Drop has expired")

    if drop.max_downloads and drop.download_count >= drop.max_downloads:
        raise HTTPException(status_code=410, detail="Drop already downloaded")

    return drop
