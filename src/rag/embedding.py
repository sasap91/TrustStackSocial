"""
Local embeddings with fastembed (MiniLM-L6-v2, 384 dim) for RAG.
"""
import os
import struct
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_embedding_model = None


def get_embedding_model():
    """Lazy-load fastembed TextEmbedding model (384 dim for sqlite-vec)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise ImportError(
                "fastembed is required for RAG. Install with: pip install fastembed"
            ) from e
        os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
        logger.info("Loading MiniLM-L6-v2 embedding model (ONNX)...")
        _embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        logger.info("Embedding model loaded")
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """Generate a 384-dimensional embedding for the given text."""
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts in a batch."""
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = list(model.embed(texts))
    return [emb.tolist() for emb in embeddings]


def serialize_embedding(embedding: List[float]) -> bytes:
    """Serialize embedding to binary format for sqlite-vec."""
    return struct.pack(f"{len(embedding)}f", *embedding)
