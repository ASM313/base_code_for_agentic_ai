"""Core RAG service using PGVector for vector similarity search.

This module provides the central RAG engine. It connects to the PostgreSQL
database (with the pgvector extension enabled), manages a single global
collection named `rag_documents`, and exposes methods for adding, searching,
and deleting documents. All embeddings are generated locally via the
EmbeddingService (qwen3-embedding:0.6b on Ollama).
"""

from typing import (
    Dict,
    List,
    Optional,
)

from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy

from src.config.settings import settings
from src.services.embedding_provider import embedding_service
from src.system.logs import logger


class RAGService:
    """Core RAG engine backed by pgvector.

    Manages a single global collection (`rag_documents`) shared across all
    users. Embeddings are generated via the local Ollama qwen3-embedding:0.6b
    model. No external API calls are made.

    Usage:
        # At application startup (called from lifespan or first use)
        await rag_service.initialize()

        # Ingest documents
        chunks_stored = await rag_service.add_documents(docs)

        # Retrieve relevant context
        results = await rag_service.similarity_search("user query")
    """

    def __init__(self):
        """Initialise the RAG service (does NOT connect to the DB yet)."""
        self._store: Optional[PGVector] = None
        self._connection_string: str = (
            f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        logger.info(
            "rag_service_created",
            collection=settings.RAG_COLLECTION_NAME,
        )

    def _get_store(self) -> PGVector:
        """Lazily initialise and return the PGVector store.

        PGVector uses a synchronous psycopg connection under the hood, so we
        initialise it on first access rather than at import time. The instance
        is cached for the lifetime of the process.

        Returns:
            PGVector: The initialised vector store.
        """
        if self._store is None:
            logger.info(
                "initializing_pgvector_store",
                collection=settings.RAG_COLLECTION_NAME,
                host=settings.POSTGRES_HOST,
            )
            self._store = PGVector(
                embeddings=embedding_service.get_embeddings(),
                collection_name=settings.RAG_COLLECTION_NAME,
                connection=self._connection_string,
                distance_strategy=DistanceStrategy.COSINE,
                # Creates the table + extension if they don't exist
                use_jsonb=True,
            )
            logger.info(
                "pgvector_store_initialized",
                collection=settings.RAG_COLLECTION_NAME,
            )
        return self._store

    def add_documents(self, documents: List[Document]) -> int:
        """Embed and store documents in the global pgvector collection.

        Args:
            documents: List of LangChain Document objects (already chunked)
                       with metadata fields: source, page, uploaded_by.

        Returns:
            int: Number of chunks successfully stored.

        Raises:
            Exception: Propagates any pgvector / embedding error.
        """
        if not documents:
            logger.warning("add_documents_called_with_empty_list")
            return 0

        store = self._get_store()
        source = documents[0].metadata.get("source", "unknown")
        logger.info("adding_documents_to_rag", source=source, count=len(documents))

        try:
            store.add_documents(documents)
            logger.info(
                "documents_added_to_rag",
                source=source,
                chunks_stored=len(documents),
            )
            return len(documents)
        except Exception as e:
            logger.error(
                "failed_to_add_documents",
                source=source,
                error=str(e),
            )
            raise

    def similarity_search(self, query: str, k: Optional[int] = None) -> List[Document]:
        """Retrieve the top-k most relevant document chunks for a query.

        Args:
            query: The natural language query string.
            k: Number of results to return. Defaults to settings.RAG_TOP_K.

        Returns:
            List[Document]: Ranked list of relevant document chunks with metadata.
        """
        k = k or settings.RAG_TOP_K
        store = self._get_store()

        logger.debug("rag_similarity_search", query_length=len(query), k=k)

        try:
            results = store.similarity_search(query, k=k)
            logger.info(
                "rag_search_completed",
                query_length=len(query),
                results_returned=len(results),
            )
            return results
        except Exception as e:
            logger.error("rag_search_failed", error=str(e), query=query[:100])
            return []

    def delete_by_source(self, source: str) -> bool:
        """Delete all document chunks belonging to a specific source PDF.

        Args:
            source: The basename of the PDF file (e.g. "company_policy.pdf").

        Returns:
            bool: True if deletion succeeded, False otherwise.
        """
        store = self._get_store()
        logger.info("deleting_documents_by_source", source=source)

        try:
            # PGVector supports filter-based deletion via the underlying store
            store.delete(filter={"source": source})
            logger.info("documents_deleted", source=source)
            return True
        except Exception as e:
            logger.error("failed_to_delete_documents", source=source, error=str(e))
            return False

    def get_collection_stats(self) -> Dict[str, object]:
        """Return basic statistics about the RAG collection.

        Returns:
            dict: {
                "collection_name": str,
                "total_chunks": int,
            }
        """
        try:
            store = self._get_store()
            # Access the underlying session to count rows
            with store._make_sync_session() as session:
                count = session.query(store.EmbeddingStore).count()
            return {
                "collection_name": settings.RAG_COLLECTION_NAME,
                "total_chunks": count,
            }
        except Exception as e:
            logger.error("rag_stats_failed", error=str(e))
            return {
                "collection_name": settings.RAG_COLLECTION_NAME,
                "total_chunks": -1,
            }


# Singleton instance — shared across the application
rag_service = RAGService()
