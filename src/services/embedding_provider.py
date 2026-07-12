"""Embedding provider using Ollama and qwen3-embedding:0.6b model.

This module provides a singleton embedding service that uses the locally running
Ollama server to generate vector embeddings via the qwen3-embedding:0.6b model.
No external API calls are made — everything runs on the local Ollama container.
"""

from typing import List

from langchain_ollama import OllamaEmbeddings

from src.config.settings import settings
from src.system.logs import logger


class EmbeddingService:
    """Singleton service for generating text embeddings via Ollama.

    Uses the qwen3-embedding:0.6b model running locally in the Ollama container.
    This service is used exclusively by the RAG pipeline for embedding both
    documents at ingestion time and queries at retrieval time.
    """

    def __init__(self):
        """Initialize the embedding service with qwen3-embedding:0.6b via Ollama."""
        self._embeddings: OllamaEmbeddings = OllamaEmbeddings(
            model=settings.RAG_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
        logger.info(
            "embedding_service_initialized",
            model=settings.RAG_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )

    def get_embeddings(self) -> OllamaEmbeddings:
        """Return the underlying OllamaEmbeddings instance.

        Returns:
            OllamaEmbeddings: The configured embeddings instance for use with
                langchain_postgres.PGVector.
        """
        return self._embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string into a vector.

        Args:
            text: The query text to embed.

        Returns:
            List[float]: The embedding vector.
        """
        logger.debug("embedding_query", text_length=len(text))
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document texts into vectors.

        Args:
            texts: List of document strings to embed.

        Returns:
            List[List[float]]: List of embedding vectors.
        """
        logger.debug("embedding_documents", count=len(texts))
        return self._embeddings.embed_documents(texts)


# Singleton instance — shared across the application
embedding_service = EmbeddingService()
