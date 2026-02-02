"""
Save embeddings to RAG DB and index Notion docs.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .db import get_rag_conn, init_rag_db
from .chunking import chunk_document
from .embedding import generate_embedding, generate_embeddings_batch, serialize_embedding

logger = logging.getLogger(__name__)

SOURCE_TYPE_NOTION = "notion"


def save_embedding(
    conn,
    source_type: str,
    content: str,
    embedding: List[float],
    source_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Save an embedding to the database (embeddings_meta + vec_embeddings; FTS5 via trigger).
    Returns row id.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO embeddings_meta (source_type, source_id, content, metadata, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            source_type,
            source_id,
            content,
            json.dumps(metadata) if metadata else None,
            datetime.now().isoformat(),
        ),
    )
    rowid = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO vec_embeddings (rowid, embedding)
        VALUES (?, ?)
        """,
        (rowid, serialize_embedding(embedding)),
    )
    conn.commit()
    return rowid


def clear_notion_embeddings(conn) -> int:
    """Delete all notion embeddings (embeddings_meta + vec_embeddings by rowid). Returns count deleted."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM embeddings_meta WHERE source_type = ?", (SOURCE_TYPE_NOTION,))
    ids = [row[0] for row in cursor.fetchall()]
    if not ids:
        return 0
    for rowid in ids:
        cursor.execute("DELETE FROM vec_embeddings WHERE rowid = ?", (rowid,))
    cursor.execute("DELETE FROM embeddings_meta WHERE source_type = ?", (SOURCE_TYPE_NOTION,))
    conn.commit()
    return len(ids)


def index_notion_docs(notion_client, db_path: Optional[str] = None) -> int:
    """
    Fetch docs from Notion, chunk, embed, and save to RAG DB.
    Clears existing notion embeddings first. Returns total chunks indexed.
    """
    conn = get_rag_conn(db_path)
    init_rag_db(conn)
    deleted = clear_notion_embeddings(conn)
    logger.info(f"Cleared {deleted} existing Notion embeddings")

    docs = notion_client.fetch_docs()
    if not docs:
        logger.warning("No Notion docs to index")
        return 0

    total = 0
    for doc in docs:
        doc_id = doc.get("id", "")
        title = doc.get("title", "Untitled")
        text = doc.get("text", "")
        if not text:
            continue
        chunks = chunk_document(text, source_id=title or doc_id)
        texts = [c["content"] for c in chunks]
        embeddings = generate_embeddings_batch(texts)
        for chunk, embedding in zip(chunks, embeddings):
            save_embedding(
                conn,
                source_type=SOURCE_TYPE_NOTION,
                content=chunk["content"],
                embedding=embedding,
                source_id=doc_id,
                metadata=chunk.get("metadata"),
            )
            total += 1
        logger.info(f"Indexed {len(chunks)} chunks from doc: {title[:50]}")
    conn.close()
    logger.info(f"Total Notion chunks indexed: {total}")
    return total
