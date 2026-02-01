"""
RAG SQLite database: sqlite-vec + FTS5 for embeddings and hybrid search.
"""
import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy load sqlite_vec to avoid import errors if not installed
_sqlite_vec = None

def _load_sqlite_vec():
    global _sqlite_vec
    if _sqlite_vec is None:
        try:
            import sqlite_vec
            _sqlite_vec = sqlite_vec
        except ImportError as e:
            raise ImportError(
                "sqlite-vec is required for RAG. Install with: pip install sqlite-vec"
            ) from e
    return _sqlite_vec


def get_rag_db_path() -> str:
    """Get the RAG database file path (separate from main app DB)."""
    db_path = os.getenv("RAG_DATABASE_PATH")
    if db_path:
        return db_path
    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / "rag.db")


def get_rag_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open RAG DB connection with sqlite-vec extension loaded."""
    path = db_path or get_rag_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    _load_sqlite_vec().load(conn)
    conn.enable_load_extension(False)
    return conn


def init_rag_db(conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """Create RAG tables: embeddings_meta, vec_embeddings (vec0), embeddings_fts (FTS5), triggers."""
    if conn is None:
        conn = get_rag_conn()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id TEXT,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
            embedding float[384] distance_metric=cosine
        )
    """)

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS embeddings_fts USING fts5(
            content,
            source_type,
            source_id,
            content='embeddings_meta',
            content_rowid='id'
        )
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS embeddings_ai AFTER INSERT ON embeddings_meta BEGIN
            INSERT INTO embeddings_fts(rowid, content, source_type, source_id)
            VALUES (new.id, new.content, new.source_type, new.source_id);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS embeddings_ad AFTER DELETE ON embeddings_meta BEGIN
            INSERT INTO embeddings_fts(embeddings_fts, rowid, content, source_type, source_id)
            VALUES ('delete', old.id, old.content, old.source_type, old.source_id);
        END
    """)

    conn.commit()
    logger.info("RAG DB initialized")
    return conn
