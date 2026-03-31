"""Search routes for semantic file search."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mvp.auth import get_current_token
from mvp.config import settings
from mvp.database import get_db
from mvp.embeddings import search_embeddings
from mvp.models import Token

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    """Request model for search."""

    query: str
    limit: int = 10


class SearchResult(BaseModel):
    """Individual search result."""

    file_id: str
    filename: str
    folder: str
    content_type: str
    relevance_score: float
    matched_chunk: str


class SearchResponse(BaseModel):
    """Response model for search."""

    results: List[SearchResult]
    total: int


@router.post("/search", response_model=SearchResponse)
def search_files(
    request: SearchRequest,
    token: Token = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Search files using semantic similarity.

    Returns files ranked by relevance to the query.
    Only searches files belonging to the authenticated token.
    """
    if not settings.google_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is not available. Google API key not configured.",
        )

    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty",
        )

    try:
        results = search_embeddings(
            db=db,
            token_id=token.id,
            query=request.query,
            limit=request.limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )

    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        total=len(results),
    )
