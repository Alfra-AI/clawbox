"""Database connection and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

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
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    except OperationalError as exc:
        db_url = make_url(settings.database_url)
        host = db_url.host or "localhost"
        port = db_url.port or 5432
        database = db_url.database or ""
        raise RuntimeError(
            "Database connection failed during startup. "
            f"Could not connect to PostgreSQL at {host}:{port}/{database}. "
            "Set DATABASE_URL to a reachable Postgres instance or start the local "
            "development database with `docker-compose up -d`, then run "
            "`alembic upgrade head`."
        ) from exc
