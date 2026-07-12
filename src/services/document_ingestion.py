"""Document ingestion service for loading and chunking PDF files.

This module handles the loading, parsing, and chunking of PDF documents
before they are stored in the pgvector knowledge base. Only PDF files
are supported, as per the project requirements.
"""

import os
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.settings import settings
from src.system.logs import logger


class DocumentIngestionService:
    """Service for loading and chunking PDF documents.

    Loads PDF pages via PyPDFLoader, splits them into overlapping chunks
    using RecursiveCharacterTextSplitter, and attaches metadata (source
    filename, page number, uploader email) to each chunk.
    """

    def __init__(self):
        """Initialize the document ingestion service with chunking settings."""
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        logger.info(
            "document_ingestion_service_initialized",
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )

    def load_pdf(self, file_path: str, uploaded_by: str = "admin") -> List[Document]:
        """Load a PDF file and split it into chunks.

        Args:
            file_path: Absolute path to the PDF file on disk.
            uploaded_by: Email of the user who uploaded the document.
                         Stored in metadata for traceability.

        Returns:
            List[Document]: List of chunked documents with metadata:
                - source: original PDF filename (basename only)
                - page: 0-indexed page number from the PDF
                - uploaded_by: email of the uploader

        Raises:
            FileNotFoundError: If the file does not exist at the given path.
            ValueError: If the file is not a PDF.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        if not file_path.lower().endswith(".pdf"):
            raise ValueError(f"Only PDF files are supported. Got: {file_path}")

        filename = os.path.basename(file_path)
        logger.info("loading_pdf", filename=filename, uploaded_by=uploaded_by)

        # Load all pages from the PDF
        loader = PyPDFLoader(file_path)
        pages: List[Document] = loader.load()

        logger.info("pdf_loaded", filename=filename, total_pages=len(pages))

        # Split pages into chunks
        chunks = self._splitter.split_documents(pages)

        # Enrich metadata on each chunk
        for chunk in chunks:
            chunk.metadata["source"] = filename
            chunk.metadata["uploaded_by"] = uploaded_by
            # PyPDFLoader sets "page" (0-indexed); keep it but normalise the key
            chunk.metadata.setdefault("page", 0)

        logger.info(
            "pdf_chunked",
            filename=filename,
            total_pages=len(pages),
            total_chunks=len(chunks),
        )
        return chunks


# Singleton instance
document_ingestion_service = DocumentIngestionService()
