"""Token management routes."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mvp.auth import get_current_token
from mvp.database import get_db
from mvp.models import Token

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


class SettingsResponse(BaseModel):
    auto_organize: bool


class SettingsUpdate(BaseModel):
    auto_organize: Optional[bool] = None


@router.get("/settings", response_model=SettingsResponse)
def get_settings(token: Token = Depends(get_current_token)) -> SettingsResponse:
    """Get current token settings."""
    return SettingsResponse(auto_organize=token.auto_organize or False)


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(
    request: SettingsUpdate,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """Update token settings."""
    if request.auto_organize is not None:
        token.auto_organize = request.auto_organize
    db.commit()
    return SettingsResponse(auto_organize=token.auto_organize or False)
