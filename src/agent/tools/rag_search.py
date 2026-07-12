"""RAG search tool for LangGraph agent.

This module exposes a LangChain @tool that the LangGraphAgent can call to
retrieve relevant information from the internal knowledge base (pgvector).
The tool returns formatted context chunks along with their source metadata,
allowing the LLM to ground its responses in uploaded documents.

No external API is used — embeddings are generated locally by the
EmbeddingService (qwen3-embedding:0.6b on Ollama).
"""

from langchain_core.tools import tool

from src.config.settings import settings
from src.services.rag_service import rag_service
from src.system.logs import logger


@tool
def rag_search(query: str) -> str:
    """Search the internal knowledge base for relevant information.

    Use this tool FIRST when the user asks about topics that may be covered
    in the organisation's internal documents, policies, manuals, or any
    uploaded PDF knowledge base. Returns the most relevant text passages
    along with the source document and page number.

    Args:
        query: A concise, specific search query describing what information
               is needed from the knowledge base.

    Returns:
        str: Formatted relevant passages from the knowledge base, each
             prefixed with source document name and page number.
             Returns "No relevant information found in the knowledge base."
             if no results match.
    """
    logger.info("rag_search_tool_invoked", query=query[:120])

    try:
        results = rag_service.similarity_search(query, k=settings.RAG_TOP_K)

        if not results:
            logger.info("rag_search_no_results", query=query[:120])
            return "No relevant information found in the knowledge base."

        # Format results into a readable context block
        formatted_chunks = []
        for i, doc in enumerate(results, start=1):
            source = doc.metadata.get("source", "Unknown source")
            page = doc.metadata.get("page", "?")
            # Pages from PyPDFLoader are 0-indexed; display as 1-indexed
            display_page = page + 1 if isinstance(page, int) else page
            content = doc.page_content.strip()

            formatted_chunks.append(
                f"[Result {i} | Source: {source} | Page: {display_page}]\n{content}"
            )

        context = "\n\n---\n\n".join(formatted_chunks)

        logger.info(
            "rag_search_tool_completed",
            query=query[:120],
            results_count=len(results),
        )
        return context

    except Exception as e:
        logger.error("rag_search_tool_failed", query=query[:120], error=str(e))
        return "Knowledge base search is temporarily unavailable. Please try again later."


# Export as the tool name used in __init__.py
rag_search_tool = rag_search
