"""
RAG (Retrieval-Augmented Generation) module: Notion docs, chunking, sqlite-vec + FTS5, hybrid search.
"""
from .db import get_rag_db_path, get_rag_conn, init_rag_db
from .chunking import chunk_document
from .embedding import get_embedding_model, generate_embedding, generate_embeddings_batch, serialize_embedding
from .store import save_embedding, index_notion_docs, clear_notion_embeddings
from .search import (
    bm25_search,
    semantic_search,
    hybrid_search,
    format_context_for_prompt,
    retrieve_context,
    RAGRetriever,
)

__all__ = [
    "get_rag_db_path",
    "get_rag_conn",
    "init_rag_db",
    "chunk_document",
    "get_embedding_model",
    "generate_embedding",
    "generate_embeddings_batch",
    "serialize_embedding",
    "save_embedding",
    "index_notion_docs",
    "clear_notion_embeddings",
    "bm25_search",
    "semantic_search",
    "hybrid_search",
    "format_context_for_prompt",
    "retrieve_context",
    "RAGRetriever",
]
