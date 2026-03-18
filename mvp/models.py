"""SQLAlchemy database models."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from mvp.config import settings
from mvp.database import Base


class Token(Base):
    """Token model for authentication and quota tracking."""

    __tablename__ = "tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    storage_used_bytes = Column(BigInteger, default=0)
    storage_limit_bytes = Column(BigInteger, default=settings.default_storage_limit_bytes)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("File", back_populates="token", cascade="all, delete-orphan")

    def has_storage_available(self, size_bytes: int) -> bool:
        """Check if the token has enough storage for the given size."""
        return (self.storage_used_bytes + size_bytes) <= self.storage_limit_bytes


class File(Base):
    """File metadata model."""

    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_id = Column(UUID(as_uuid=True), ForeignKey("tokens.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    token = relationship("Token", back_populates="files")
    embeddings = relationship("FileEmbedding", back_populates="file", cascade="all, delete-orphan")


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
