"""Database connection and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from mvp.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_pgvector_extension() -> None:
    """Ensure the pgvector extension exists.

    Schema creation and upgrades are handled by Alembic migrations.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
