"""
Chunk documents by ## headers for RAG (matches workshop notebook).
"""
import re
from typing import List, Dict, Any


def chunk_document(content: str, source_id: str) -> List[Dict[str, Any]]:
    """
    Chunk a markdown document by ## headers.

    Each chunk includes:
    - The document title (# header) for context
    - The section content
    - Metadata about the source
    """
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    doc_title = title_match.group(1).strip() if title_match else source_id

    sections = re.split(r"(?=^##\s+)", content, flags=re.MULTILINE)

    chunks: List[Dict[str, Any]] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        section_title_match = re.search(r"^##\s+(.+)$", section, re.MULTILINE)
        section_title = section_title_match.group(1).strip() if section_title_match else "Introduction"
        chunk_content = f"[From: {source_id}]\n# {doc_title}\n\n{section}"
        chunks.append({
            "content": chunk_content,
            "metadata": {
                "source_file": source_id,
                "section_title": section_title,
            },
        })
    if not chunks:
        chunks = [{"content": content, "metadata": {"source_file": source_id}}]
    return chunks
