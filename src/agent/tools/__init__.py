"""LangGraph tools for enhanced language model capabilities.

This package contains custom tools that can be used with LangGraph to extend
the capabilities of language models. Includes tools for web search and
internal knowledge base retrieval (RAG).
"""

from langchain_core.tools.base import BaseTool

# from .web_search import duckduckgo_search_tool
from .rag_search import rag_search_tool

# tools: list[BaseTool] = [rag_search_tool, duckduckgo_search_tool]
tools: list[BaseTool] = [rag_search_tool]
