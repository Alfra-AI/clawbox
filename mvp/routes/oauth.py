"""Google OAuth authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.requests import Request

from mvp.auth import get_current_token
from mvp.config import settings
from mvp.database import get_db
from mvp.models import Token, User
from mvp.oauth import oauth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def google_login(request: Request):
    """Redirect to Google OAuth consent screen."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    redirect_uri = f"{settings.app_url}/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    token_data = await oauth.google.authorize_access_token(request)
    user_info = token_data.get("userinfo")
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from Google",
        )

    google_id = user_info["sub"]
    email = user_info["email"]
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    # Find or create user
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            picture_url=picture,
        )
        db.add(user)
        db.flush()
    else:
        # Update user info on each login
        user.email = email
        user.name = name
        user.picture_url = picture

    # Find or create token for this user
    api_token = db.query(Token).filter(Token.user_id == user.id).first()
    if not api_token:
        api_token = Token(user_id=user.id)
        db.add(api_token)

    db.commit()

    # Redirect to frontend with token
    return RedirectResponse(url=f"{settings.app_url}/?token={api_token.id}")


@router.get("/me")
def get_current_user(
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
):
    """Get the current user's info (if token is linked to a Google account)."""
    if not token.user_id:
        return {"anonymous": True}

    user = db.query(User).filter(User.id == token.user_id).first()
    if not user:
        return {"anonymous": True}

    return {
        "anonymous": False,
        "email": user.email,
        "name": user.name,
        "picture_url": user.picture_url,
    }


@router.get("/providers")
def get_auth_providers():
    """Return which auth providers are available."""
    return {
        "google": bool(settings.google_client_id and settings.google_client_secret),
    }
