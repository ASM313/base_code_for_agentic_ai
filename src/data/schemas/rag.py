"""Pydantic schemas for RAG (Retrieval-Augmented Generation) API endpoints.

These schemas define the request and response shapes for the RAG REST API,
covering document upload, similarity search, document deletion, and
collection statistics.
"""

from typing import List

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response returned after successfully ingesting a PDF document.

    Attributes:
        filename: Name of the uploaded PDF file.
        chunks_stored: Number of text chunks embedded and stored in pgvector.
        message: Human-readable status message.
    """

    filename: str
    chunks_stored: int
    message: str


class RAGSearchRequest(BaseModel):
    """Request body for the manual RAG search endpoint.

    Attributes:
        query: Natural language search query.
        k: Number of results to return (1–20). Defaults to 5.
    """

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    k: int = Field(default=5, ge=1, le=20, description="Number of results to return")


class RAGSearchResult(BaseModel):
    """A single retrieved document chunk.

    Attributes:
        content: The text content of the chunk.
        source: Source PDF filename.
        page: 1-indexed page number within the source PDF.
    """

    content: str
    source: str
    page: int


class RAGSearchResponse(BaseModel):
    """Response from the manual RAG search endpoint.

    Attributes:
        query: The original search query.
        results: List of retrieved document chunks.
        total_results: Number of chunks returned.
    """

    query: str
    results: List[RAGSearchResult]
    total_results: int


class RAGDeleteRequest(BaseModel):
    """Request body for deleting documents from the knowledge base.

    Attributes:
        source: Exact basename of the PDF file to delete (e.g. "policy.pdf").
                All chunks belonging to this source will be removed.
    """

    source: str = Field(..., min_length=1, description="PDF filename to delete (basename only)")


class RAGStatsResponse(BaseModel):
    """Response from the collection statistics endpoint.

    Attributes:
        collection_name: Name of the pgvector collection.
        total_chunks: Total number of chunks stored in the collection.
    """

    collection_name: str
    total_chunks: int
