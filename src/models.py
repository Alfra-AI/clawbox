"""SQLAlchemy database models."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config import settings
from src.database import Base


class User(Base):
    """User model for Google OAuth accounts."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    picture_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tokens = relationship("Token", back_populates="user")


class Token(Base):
    """Token model for authentication and quota tracking."""

    __tablename__ = "tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    storage_used_bytes = Column(BigInteger, default=0)
    storage_limit_bytes = Column(BigInteger, default=settings.default_storage_limit_bytes)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tokens")
    files = relationship("File", back_populates="token", cascade="all, delete-orphan")
    embedding_jobs = relationship("EmbeddingJob", back_populates="token", cascade="all, delete-orphan")

    def has_storage_available(self, size_bytes: int) -> bool:
        """Check if the token has enough storage for the given size."""
        return (self.storage_used_bytes + size_bytes) <= self.storage_limit_bytes


class File(Base):
    """File metadata model."""

    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_id = Column(UUID(as_uuid=True), ForeignKey("tokens.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    folder = Column(String(1024), nullable=False, default="/")
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(512), nullable=False)
    embedding_status = Column(String(20), nullable=False)
    last_embedded_at = Column(DateTime, nullable=True)
    embedding_error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    token = relationship("Token", back_populates="files")
    embeddings = relationship("FileEmbedding", back_populates="file", cascade="all, delete-orphan")
    embedding_jobs = relationship("EmbeddingJob", back_populates="file", cascade="all, delete-orphan")


class EmbeddingJob(Base):
    """Durable file embedding job."""

    __tablename__ = "embedding_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    token_id = Column(UUID(as_uuid=True), ForeignKey("tokens.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=settings.embedding_job_max_attempts)
    priority = Column(Integer, nullable=False, default=100)
    requested_by = Column(String(20), nullable=False, default="system")
    error_code = Column(String(100), nullable=True)
    error_detail = Column(Text, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    file = relationship("File", back_populates="embedding_jobs")
    token = relationship("Token", back_populates="embedding_jobs")

    __table_args__ = (
        Index("ix_embedding_jobs_status_priority_created", "status", "priority", "created_at"),
    )


class FileEmbedding(Base):
    """Vector embeddings for semantic search."""

    __tablename__ = "file_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.embedding_dimensions), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("File", back_populates="embeddings")


class SharedLink(Base):
    """Shared link for public file access."""

    __tablename__ = "shared_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(10), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    max_downloads = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("File")


class DropSession(Base):
    """Ephemeral drop session — text + multiple files, 10-min expiry."""

    __tablename__ = "drop_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(4), unique=True, nullable=False, index=True)
    text_content = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("DropFile", back_populates="session", cascade="all, delete-orphan")


class DropFile(Base):
    """File attached to a drop session."""

    __tablename__ = "drop_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("drop_sessions.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("DropSession", back_populates="files")
