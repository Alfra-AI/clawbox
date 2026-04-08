"""Quick Drop routes — ephemeral text + file sharing with 4-digit PIN."""

import random
from datetime import datetime, timedelta
from io import BytesIO
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mvp.database import get_db
from mvp.models import DropFile, DropSession
from mvp.storage import get_storage_backend

router = APIRouter(prefix="/drop", tags=["drop"])

MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200 MB total per drop
MAX_TEXT_SIZE = 100_000  # 100K chars (~100 KB)
EXPIRY_MINUTES = 10


def _generate_code(db: Session) -> str:
    """Generate a unique 4-digit PIN code."""
    for _ in range(100):
        code = f"{random.randint(0, 9999):04d}"
        exists = db.query(DropSession).filter(DropSession.code == code).first()
        if not exists:
            return code
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Too many active drops, try again later",
    )


def _cleanup_expired(db: Session):
    """Delete expired sessions."""
    expired = db.query(DropSession).filter(DropSession.expires_at < datetime.utcnow()).all()
    for session in expired:
        db.delete(session)
    if expired:
        db.commit()


def _get_valid_session(code: str, db: Session) -> DropSession:
    """Look up a drop session by code, checking expiry."""
    _cleanup_expired(db)
    session = db.query(DropSession).filter(DropSession.code == code).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Drop not found or expired")
    if datetime.utcnow() > session.expires_at:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=410, detail="Drop has expired")
    return session


# --- Response models ---

class DropFileInfo(BaseModel):
    id: str
    filename: str
    size_bytes: int
    content_type: str


class DropCreateResponse(BaseModel):
    code: str
    expires_at: datetime
    text: Optional[str] = None
    files: List[DropFileInfo]


class DropInfoResponse(BaseModel):
    code: str
    text: Optional[str] = None
    files: List[DropFileInfo]
    expires_at: datetime


# --- Endpoints ---

@router.post("", response_model=DropCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_drop(
    text: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    """Create a drop with text and/or files. No auth needed. Expires in 10 minutes."""
    if not text and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide text and/or files",
        )

    if text and len(text) > MAX_TEXT_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Text too long. Max {MAX_TEXT_SIZE:,} characters.",
        )

    _cleanup_expired(db)

    code = _generate_code(db)
    expires_at = datetime.utcnow() + timedelta(minutes=EXPIRY_MINUTES)

    session = DropSession(
        code=code,
        text_content=text,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()

    # Process files
    storage = get_storage_backend()
    total_size = 0
    drop_files = []
    namespace = uuid4()  # shared namespace for this drop's files

    for upload_file in files:
        content = await upload_file.read()
        total_size += len(content)

        if total_size > MAX_TOTAL_SIZE:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total file size exceeds {MAX_TOTAL_SIZE // (1024*1024)} MB",
            )

        file_id = uuid4()
        storage_path = await storage.save(
            token_id=namespace,
            file_id=file_id,
            file_data=BytesIO(content),
            filename=upload_file.filename or "unnamed",
        )

        drop_file = DropFile(
            id=file_id,
            session_id=session.id,
            filename=upload_file.filename or "unnamed",
            content_type=upload_file.content_type or "application/octet-stream",
            size_bytes=len(content),
            storage_path=storage_path,
        )
        db.add(drop_file)
        drop_files.append(drop_file)

    db.commit()

    return DropCreateResponse(
        code=code,
        expires_at=expires_at,
        text=text,
        files=[
            DropFileInfo(
                id=str(f.id),
                filename=f.filename,
                size_bytes=f.size_bytes,
                content_type=f.content_type,
            )
            for f in drop_files
        ],
    )


@router.get("/{code}", response_model=DropInfoResponse)
def get_drop(code: str, db: Session = Depends(get_db)):
    """Get drop contents — text and file list."""
    session = _get_valid_session(code, db)

    return DropInfoResponse(
        code=session.code,
        text=session.text_content,
        files=[
            DropFileInfo(
                id=str(f.id),
                filename=f.filename,
                size_bytes=f.size_bytes,
                content_type=f.content_type,
            )
            for f in session.files
        ],
        expires_at=session.expires_at,
    )


@router.get("/{code}/file/{file_id}")
async def download_drop_file(code: str, file_id: str, db: Session = Depends(get_db)):
    """Download a specific file from a drop."""
    session = _get_valid_session(code, db)

    drop_file = None
    for f in session.files:
        if str(f.id) == file_id:
            drop_file = f
            break

    if drop_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    storage = get_storage_backend()
    try:
        content = await storage.load(drop_file.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in storage")

    return Response(
        content=content,
        media_type=drop_file.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{drop_file.filename}"',
        },
    )
