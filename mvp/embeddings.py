"""Embeddings generation and management using OpenAI."""

import io
import logging
from typing import List, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from mvp.config import settings
from mvp.models import File, FileEmbedding

logger = logging.getLogger(__name__)

# Chunk size for text splitting (in characters)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def extract_text_from_pdf(content: bytes) -> Optional[str]:
    """Extract text from PDF content."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts) if text_parts else None
    except Exception:
        return None


def get_openai_client() -> OpenAI:
    """Get OpenAI client instance."""
    return OpenAI(api_key=settings.openai_api_key)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text using OpenAI."""
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")

    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts in a single API call."""
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")

    if not texts:
        return []

    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def generate_and_store_embeddings(
    db: Session, file: File, content: bytes, content_type: str
) -> bool:
    """Generate embeddings for file content and store them.

    Returns True if embeddings were generated successfully (or file was empty),
    False if embedding generation failed.
    """
    text = None

    # Handle PDF files
    if content_type == "application/pdf":
        text = extract_text_from_pdf(content)
        if text is None:
            logger.warning("Failed to extract text from PDF %s", file.id)
            return False
    else:
        # Decode content to text
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception:
                logger.warning("Failed to decode file %s for embedding", file.id)
                return False

    if not text or not text.strip():
        return True  # Empty file, nothing to embed

    # Chunk the text
    chunks = chunk_text(text)

    # Generate embeddings
    try:
        embeddings = generate_embeddings_batch(chunks)
    except Exception:
        logger.exception("Failed to generate embeddings for file %s", file.id)
        return False

    # Store embeddings
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        file_embedding = FileEmbedding(
            file_id=file.id,
            chunk_index=i,
            chunk_text=chunk,
            embedding=embedding,
        )
        db.add(file_embedding)

    return True


def search_embeddings(db: Session, token_id: str, query: str, limit: int = 10) -> List[dict]:
    """Search for files matching the query using vector similarity."""
    # Generate embedding for query
    query_embedding = generate_embedding(query)

    # Search using pgvector cosine distance
    from sqlalchemy import select, func
    from mvp.models import FileEmbedding, File

    # Query with vector similarity
    results = (
        db.query(
            FileEmbedding,
            File,
            FileEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .join(File, FileEmbedding.file_id == File.id)
        .filter(File.token_id == token_id)
        .order_by("distance")
        .limit(limit)
        .all()
    )

    # Deduplicate by file and format results
    seen_files = set()
    formatted_results = []

    for embedding, file, distance in results:
        if file.id in seen_files:
            continue
        seen_files.add(file.id)

        formatted_results.append({
            "file_id": str(file.id),
            "filename": file.filename,
            "content_type": file.content_type,
            "relevance_score": 1 - distance,  # Convert distance to similarity
            "matched_chunk": embedding.chunk_text[:200] + "..." if len(embedding.chunk_text) > 200 else embedding.chunk_text,
        })

    return formatted_results
