"""Main FastAPI application for AgentBox."""

from contextlib import asynccontextmanager
from pathlib import Path

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
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
from mvp.routes import drops, files, oauth, search, tokens
from mvp.storage import get_storage_backend

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    ensure_pgvector_extension()
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
app.include_router(drops.router)


@app.get("/")
async def index():
    """Serve the web UI."""
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


@app.get("/d/{code}")
async def drop_page(code: str):
    """Serve the drop download page."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ClawBox Drop</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
               min-height: 100vh; color: #e0e0e0; display: flex; align-items: center; justify-content: center; }}
        .card {{ background: rgba(255,255,255,0.05); border-radius: 16px; padding: 40px;
                border: 1px solid rgba(255,255,255,0.1); text-align: center; max-width: 400px; width: 90%; }}
        h1 {{ color: #00d4ff; font-size: 1.5rem; margin-bottom: 8px; }}
        .code {{ font-size: 3rem; font-weight: 700; color: #4ade80; letter-spacing: 0.3em;
                margin: 20px 0; font-family: 'Monaco','Menlo',monospace; }}
        .meta {{ color: #888; font-size: 0.9rem; margin-bottom: 24px; }}
        .filename {{ color: #e0e0e0; font-size: 1.1rem; margin-bottom: 8px; word-break: break-all; }}
        button {{ background: linear-gradient(135deg, #00d4ff, #0099cc); color: #fff; border: none;
                 padding: 14px 40px; border-radius: 8px; cursor: pointer; font-size: 1.1rem;
                 font-weight: 600; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,212,255,0.3); }}
        .error {{ color: #ef4444; }}
        .expired {{ opacity: 0.6; }}
    </style>
</head>
<body>
    <div class="card" id="dropCard">
        <h1>ClawBox Drop</h1>
        <div class="code">{code}</div>
        <div id="info"><div class="meta">Loading...</div></div>
    </div>
    <script>
        const code = "{code}";
        const API = window.location.origin;
        fetch(`${{API}}/drop/${{code}}`).then(r => {{
            if (!r.ok) return r.json().then(d => {{ throw d; }});
            return r.json();
        }}).then(data => {{
            document.getElementById('info').innerHTML = `
                <div class="filename">${{data.filename}}</div>
                <div class="meta">${{formatBytes(data.size_bytes)}}${{data.downloads_remaining != null ? ' · ' + data.downloads_remaining + ' download(s) left' : ''}}</div>
                <button onclick="dl()">Download</button>
            `;
        }}).catch(err => {{
            document.getElementById('info').innerHTML = `<div class="error">${{err.detail || 'Drop not found'}}</div>`;
        }});
        function dl() {{ window.location.href = `${{API}}/drop/${{code}}/download`; }}
        function formatBytes(b) {{
            if (b === 0) return '0 B';
            const k = 1024, s = ['B','KB','MB','GB'];
            const i = Math.floor(Math.log(b) / Math.log(k));
            return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + s[i];
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


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
