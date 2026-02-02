"""
Hybrid search (BM25 + semantic) and RAG retrieval.
"""
import json
import sqlite3
import logging
from typing import Any, Dict, List, Optional

from .db import get_rag_db_path, get_rag_conn
from .embedding import generate_embedding, serialize_embedding

logger = logging.getLogger(__name__)


def bm25_search(conn: sqlite3.Connection, query: str, limit: int = 100) -> Dict[int, float]:
    """BM25 search via FTS5. Returns dict mapping rowid to raw BM25 score (negative = better)."""
    cursor = conn.cursor()
    safe_query = query.replace('"', '""')
    try:
        cursor.execute(
            """
            SELECT rowid, bm25(embeddings_fts) as score
            FROM embeddings_fts
            WHERE embeddings_fts MATCH ?
            LIMIT ?
            """,
            (safe_query, limit),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return {}


def semantic_search(
    conn: sqlite3.Connection, query_embedding: List[float], limit: int = 100
) -> Dict[int, float]:
    """Semantic search via sqlite-vec cosine distance. Returns dict mapping rowid to distance."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT rowid, distance
        FROM vec_embeddings
        WHERE embedding MATCH ?
          AND k = ?
        ORDER BY distance
        """,
        (serialize_embedding(query_embedding), limit),
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def normalize_bm25_scores(bm25_scores: Dict[int, float]) -> Dict[int, float]:
    """Normalize BM25 (negative = better) to [0, 1] (best = 1)."""
    if not bm25_scores:
        return {}
    scores = list(bm25_scores.values())
    min_score = min(scores)
    max_score = max(scores)
    if min_score == max_score:
        return {k: 1.0 for k in bm25_scores}
    return {
        k: (max_score - v) / (max_score - min_score)
        for k, v in bm25_scores.items()
    }


def normalize_distances(distances: Dict[int, float]) -> Dict[int, float]:
    """Convert cosine distances to [0, 1] similarity (best = 1)."""
    if not distances:
        return {}
    similarities = {k: 1 - (v / 2) for k, v in distances.items()}
    min_sim = min(similarities.values())
    max_sim = max(similarities.values())
    if min_sim == max_sim:
        return {k: 1.0 for k in similarities}
    return {
        k: (s - min_sim) / (max_sim - min_sim)
        for k, s in similarities.items()
    }


def get_metadata_by_ids(conn: sqlite3.Connection, ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Fetch embeddings_meta rows by id."""
    if not ids:
        return {}
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(ids))
    cursor.execute(
        f"""
        SELECT id, source_type, source_id, content, metadata
        FROM embeddings_meta
        WHERE id IN ({placeholders})
        """,
        ids,
    )
    out = {}
    for row in cursor.fetchall():
        out[row[0]] = {
            "source_type": row[1],
            "source_id": row[2],
            "content": row[3],
            "metadata": json.loads(row[4]) if row[4] else {},
        }
    return out


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    query_embedding: List[float],
    keyword_weight: float = 0.5,
    semantic_weight: float = 0.5,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Combine BM25 and semantic scores; return top_k results with content and scores."""
    bm25_raw = bm25_search(conn, query)
    bm25_norm = normalize_bm25_scores(bm25_raw)
    semantic_raw = semantic_search(conn, query_embedding, limit=100)
    semantic_norm = normalize_distances(semantic_raw)
    all_ids = set(bm25_norm.keys()) | set(semantic_norm.keys())
    if not all_ids:
        return []
    meta = get_metadata_by_ids(conn, list(all_ids))
    scored = []
    for id in all_ids:
        bm25_s = bm25_norm.get(id, 0.0)
        sem_s = semantic_norm.get(id, 0.0)
        final = keyword_weight * bm25_s + semantic_weight * sem_s
        m = meta.get(id, {})
        scored.append({
            "id": id,
            "content": m.get("content", ""),
            "source_type": m.get("source_type", ""),
            "source_id": m.get("source_id", ""),
            "metadata": m.get("metadata", {}),
            "bm25_score": bm25_s,
            "semantic_score": sem_s,
            "final_score": final,
        })
    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored[:top_k]


def format_context_for_prompt(results: List[Dict[str, Any]], max_chars: int = 4000) -> str:
    """Format hybrid search results as context string for LLM."""
    if not results:
        return "No relevant context found."
    parts = []
    used = 0
    for i, r in enumerate(results, 1):
        header = f"[{i}. {r['source_type']}] (score: {r['final_score']:.2f})"
        content = r["content"]
        available = max_chars - used - len(header) - 10
        if available <= 100:
            break
        if len(content) > available:
            content = content[: available - 3] + "..."
        parts.append(f"{header}\n{content}\n")
        used += len(parts[-1])
    return "\n".join(parts)


def retrieve_context(
    conn: Optional[sqlite3.Connection] = None,
    query: str = "TrustStack company information",
    top_k: int = 5,
    db_path: Optional[str] = None,
) -> tuple:
    """Retrieve and format context for RAG. Returns (formatted_string, results_list)."""
    if conn is None:
        conn = get_rag_conn(db_path)
        own_conn = True
    else:
        own_conn = False
    try:
        query_embedding = generate_embedding(query)
        results = hybrid_search(conn, query, query_embedding, top_k=top_k)
        formatted = format_context_for_prompt(results)
        return formatted, results
    finally:
        if own_conn:
            conn.close()


class RAGRetriever:
    """Retriever that uses RAG DB for hybrid search; can be passed to PostGenerator."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_rag_db_path()

    def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        keyword_weight: float = 0.5,
        semantic_weight: float = 0.5,
    ) -> tuple:
        """Return (formatted_context_str, results_list)."""
        conn = get_rag_conn(self.db_path)
        try:
            query_embedding = generate_embedding(query)
            results = hybrid_search(
                conn, query, query_embedding,
                keyword_weight=keyword_weight,
                semantic_weight=semantic_weight,
                top_k=top_k,
            )
            return format_context_for_prompt(results), results
        finally:
            conn.close()
