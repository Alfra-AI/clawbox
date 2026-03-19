"""Main FastAPI application for AgentBox."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mvp import __version__
from mvp.database import init_db
from mvp.routes import files, search, tokens

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    init_db()
    yield
    # Shutdown


app = FastAPI(
    title="AgentBox",
    description="A minimal cloud file system for agents with semantic search capabilities.",
    version=__version__,
    lifespan=lifespan,
)

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


@app.get("/")
async def index():
    """Serve the web UI."""
    return FileResponse(STATIC_DIR / "index.html")


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
