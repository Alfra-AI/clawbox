"""Google OAuth configuration using Authlib."""

from authlib.integrations.starlette_client import OAuth

from mvp.config import settings

oauth = OAuth()


def register_google():
    """Register Google OAuth provider if credentials are configured."""
    if settings.google_client_id and settings.google_client_secret:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
