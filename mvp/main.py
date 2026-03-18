"""Main FastAPI application for AgentBox."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mvp import __version__
from mvp.database import init_db
from mvp.routes import files, search, tokens


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

# Include routers
app.include_router(tokens.router)
app.include_router(files.router)
app.include_router(search.router)


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
