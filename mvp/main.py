"""Main FastAPI application for AgentBox."""

from contextlib import asynccontextmanager
from pathlib import Path

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse as StaticFileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from mvp import __version__
from mvp.config import settings
from mvp.database import ensure_pgvector_extension, get_db
from mvp.models import SharedLink, File as FileModel
from mvp.oauth import register_google
from mvp.routes import files, oauth, search, tokens
from mvp.storage import get_storage_backend

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    ensure_pgvector_extension()
    # Auto-run database migrations
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command
        alembic_cfg = AlembicConfig("alembic.ini")
        command.upgrade(alembic_cfg, "head")
    except Exception:
        pass  # alembic.ini may not exist in some deployments
    register_google()
    yield
    # Shutdown


app = FastAPI(
    title="AgentBox",
    description="A minimal cloud file system for agents with semantic search capabilities.",
    version=__version__,
    lifespan=lifespan,
)

# Session middleware (for OAuth state during redirect flow)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tokens.router)
app.include_router(files.router)
app.include_router(search.router)
app.include_router(oauth.router)


DROP_DOMAINS = {"qdrop.cc", "www.qdrop.cc"}


@app.get("/")
async def index(request: Request):
    """Serve the web UI, or drop page if accessed via qdrop.cc."""
    host = request.headers.get("host", "").split(":")[0]
    if host in DROP_DOMAINS:
        return StaticFileResponse(STATIC_DIR / "drop.html")
    return StaticFileResponse(STATIC_DIR / "index.html")


@app.get("/s/{code}")
async def shared_download(code: str, db: Session = Depends(get_db)):
    """Download a file via shared link (no auth required)."""
    link = db.query(SharedLink).filter(SharedLink.code == code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found or expired")

    # Check expiry
    if link.expires_at and datetime.utcnow() > link.expires_at:
        db.delete(link)
        db.commit()
        raise HTTPException(status_code=410, detail="Link has expired")

    # Check download limit
    if link.max_downloads and link.download_count >= link.max_downloads:
        raise HTTPException(status_code=410, detail="Download limit reached")

    file_record = db.query(FileModel).filter(FileModel.id == link.file_id).first()
    if file_record is None:
        raise HTTPException(status_code=404, detail="File no longer exists")

    storage = get_storage_backend()
    try:
        content = await storage.load(file_record.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in storage")

    # Increment download count
    link.download_count += 1
    db.commit()

    return Response(
        content=content,
        media_type=file_record.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.filename}"',
        },
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


if __name__ == "__main__":
    import uvicorn
    from mvp.config import settings

    uvicorn.run(
        "mvp.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
