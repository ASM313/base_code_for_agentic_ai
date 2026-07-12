"""RAG (Retrieval-Augmented Generation) API endpoints.

All endpoints in this router are restricted to admin users only (is_admin=True).
Regular users can benefit from the RAG knowledge base via the chat interface,
but only admins can manage (upload / delete) the documents.

Endpoints:
    POST   /rag/upload     - Upload and ingest a PDF into the knowledge base
    POST   /rag/search     - Manually query the knowledge base (admin testing)
    DELETE /rag/document   - Remove all chunks for a given PDF source
    GET    /rag/stats      - Collection statistics
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import List

import aiofiles
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
)

from src.config.settings import settings
from src.data.models.user import User
from src.data.schemas.rag import (
    DocumentUploadResponse,
    RAGDeleteRequest,
    RAGSearchRequest,
    RAGSearchResponse,
    RAGSearchResult,
    RAGStatsResponse,
)
from src.interface.auth import get_admin_user
from src.services.document_ingestion import document_ingestion_service
from src.services.rag_service import rag_service
from src.system.logs import logger
from src.system.rate_limit import limiter

router = APIRouter()

# Maximum PDF size: 50 MB
MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.post("/upload", response_model=DocumentUploadResponse)
@limiter.limit("20 per hour")
async def upload_document(
    request: Request,
    file: UploadFile,
    admin: User = Depends(get_admin_user),
):
    """Upload a PDF document and ingest it into the RAG knowledge base.

    The PDF is temporarily saved to disk, parsed, chunked, embedded via
    qwen3-embedding:0.6b (Ollama), and stored in pgvector. The temporary
    file is deleted after ingestion regardless of success or failure.

    Args:
        request: FastAPI request object (required by SlowAPI rate limiter).
        file: The uploaded PDF file (multipart/form-data).
        admin: Authenticated admin user (403 if not admin).

    Returns:
        DocumentUploadResponse: Filename, chunk count, and status message.

    Raises:
        HTTPException 400: If the file is not a PDF or exceeds the size limit.
        HTTPException 500: If ingestion fails.
    """
    # --- Validate file type ---
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are accepted. Received content-type: {file.content_type}",
        )

    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="File must have a .pdf extension.",
        )

    # Sanitise filename to avoid path traversal
    safe_filename = Path(filename).name

    # Ensure upload directory exists
    upload_dir = Path(settings.RAG_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Use a unique temp name to avoid collisions in concurrent uploads
    temp_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    temp_path = upload_dir / temp_filename

    logger.info(
        "rag_upload_started",
        filename=safe_filename,
        admin_email=admin.email,
        temp_path=str(temp_path),
    )

    try:
        # --- Save uploaded file to disk ---
        total_bytes = 0
        async with aiofiles.open(temp_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):  # Read in 1 MB chunks
                total_bytes += len(chunk)
                if total_bytes > MAX_PDF_SIZE_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds the maximum allowed size of {MAX_PDF_SIZE_BYTES // (1024*1024)} MB.",
                    )
                await out_file.write(chunk)

        logger.info(
            "rag_file_saved",
            filename=safe_filename,
            size_bytes=total_bytes,
        )

        # --- Load, chunk, and ingest ---
        chunks = document_ingestion_service.load_pdf(
            file_path=str(temp_path),
            uploaded_by=admin.email,
        )

        # Override the source metadata to use the original filename (not the temp name)
        for chunk in chunks:
            chunk.metadata["source"] = safe_filename

        chunks_stored = rag_service.add_documents(chunks)

        logger.info(
            "rag_upload_complete",
            filename=safe_filename,
            chunks_stored=chunks_stored,
            admin_email=admin.email,
        )

        return DocumentUploadResponse(
            filename=safe_filename,
            chunks_stored=chunks_stored,
            message=f"Successfully ingested '{safe_filename}' into the knowledge base ({chunks_stored} chunks).",
        )

    except HTTPException:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(
            "rag_upload_failed",
            filename=safe_filename,
            error=str(e),
            admin_email=admin.email,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest document: {str(e)}",
        )
    finally:
        # Always clean up the temp file
        if temp_path.exists():
            temp_path.unlink()
            logger.debug("rag_temp_file_deleted", temp_path=str(temp_path))


@router.post("/search", response_model=RAGSearchResponse)
@limiter.limit("60 per minute")
async def search_knowledge_base(
    request: Request,
    search_request: RAGSearchRequest,
    admin: User = Depends(get_admin_user),
):
    """Manually query the RAG knowledge base (for admin testing / debugging).

    This endpoint allows admins to directly test what the retrieval pipeline
    returns for a given query, without going through the chat interface.

    Args:
        request: FastAPI request object (rate limiting).
        search_request: Query string and optional k (number of results).
        admin: Authenticated admin user.

    Returns:
        RAGSearchResponse: Query echoed back with list of retrieved chunks.
    """
    logger.info(
        "rag_manual_search",
        query=search_request.query[:100],
        k=search_request.k,
        admin_email=admin.email,
    )

    try:
        docs = rag_service.similarity_search(search_request.query, k=search_request.k)

        results: List[RAGSearchResult] = [
            RAGSearchResult(
                content=doc.page_content.strip(),
                source=doc.metadata.get("source", "unknown"),
                page=int(doc.metadata.get("page", 0)) + 1,  # Convert to 1-indexed
            )
            for doc in docs
        ]

        return RAGSearchResponse(
            query=search_request.query,
            results=results,
            total_results=len(results),
        )

    except Exception as e:
        logger.error("rag_manual_search_failed", error=str(e), admin_email=admin.email)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.delete("/document", status_code=200)
@limiter.limit("30 per hour")
async def delete_document(
    request: Request,
    delete_request: RAGDeleteRequest,
    admin: User = Depends(get_admin_user),
):
    """Delete all chunks for a given PDF source from the knowledge base.

    Args:
        request: FastAPI request object (rate limiting).
        delete_request: Contains the source PDF filename to delete.
        admin: Authenticated admin user.

    Returns:
        dict: Confirmation message.

    Raises:
        HTTPException 500: If deletion fails.
    """
    logger.info(
        "rag_delete_document",
        source=delete_request.source,
        admin_email=admin.email,
    )

    success = rag_service.delete_by_source(delete_request.source)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document '{delete_request.source}' from knowledge base.",
        )

    return {"message": f"All chunks for '{delete_request.source}' have been deleted from the knowledge base."}


@router.get("/stats", response_model=RAGStatsResponse)
@limiter.limit("30 per minute")
async def get_rag_stats(
    request: Request,
    admin: User = Depends(get_admin_user),
):
    """Return statistics about the RAG knowledge base collection.

    Args:
        request: FastAPI request object (rate limiting).
        admin: Authenticated admin user.

    Returns:
        RAGStatsResponse: Collection name and total chunk count.
    """
    logger.info("rag_stats_requested", admin_email=admin.email)

    try:
        stats = rag_service.get_collection_stats()
        return RAGStatsResponse(
            collection_name=stats["collection_name"],
            total_chunks=stats["total_chunks"],
        )
    except Exception as e:
        logger.error("rag_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")
