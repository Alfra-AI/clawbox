"""Token management routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Token

router = APIRouter()


class TokenResponse(BaseModel):
    """Response model for token creation."""

    token: str
    storage_limit_bytes: int
    storage_used_bytes: int

    class Config:
        from_attributes = True


@router.post("/get_token", response_model=TokenResponse)
def create_token(db: Session = Depends(get_db)) -> TokenResponse:
    """Create a new token with default storage quota.

    This endpoint requires no authentication and provides a free token
    with 10 MB of storage.
    """
    token = Token()
    db.add(token)
    db.commit()
    db.refresh(token)

    return TokenResponse(
        token=str(token.id),
        storage_limit_bytes=token.storage_limit_bytes,
        storage_used_bytes=token.storage_used_bytes,
    )
