"""Section-aware chunking for SOP-style documents."""

from __future__ import annotations

import re

from app.core.config import settings


def chunk_text(
    document_id: str,
    title: str,
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[dict]:
    """Split text on headings/paragraphs, then pack into overlapping windows.

    Args:
        document_id: Source document id.
        title: Document title, prefixed into each chunk for retrieval.
        text: Raw document body.
        chunk_size: Max characters per chunk.
        overlap: Characters copied from the previous chunk.

    Returns:
        List of chunk dicts with chunk_id, content, and chunk_index.
    """
    size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.CHUNK_OVERLAP
    cleaned = text.strip()
    if not cleaned:
        return []

    sections = _split_sections(cleaned)
    windows = _pack_windows(sections, size, overlap)
    chunks: list[dict] = []
    for index, window in enumerate(windows):
        body = window.strip()
        content = f"{title}\n\n{body}" if not body.startswith(title) else body
        chunks.append(
            {
                "chunk_id": f"{document_id}:{index}",
                "document_id": document_id,
                "title": title,
                "content": content,
                "chunk_index": index,
            }
        )
    return chunks


def _split_sections(text: str) -> list[str]:
    """Split on markdown headings or blank lines."""
    heading_split = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    parts = [p.strip() for p in heading_split if p.strip()]
    if len(parts) > 1:
        return parts

    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()] or [text]


def _pack_windows(sections: list[str], size: int, overlap: int) -> list[str]:
    """Greedy pack sections into windows of at most `size` characters."""
    windows: list[str] = []
    current = ""
    for section in sections:
        if len(section) > size:
            if current:
                windows.append(current.strip())
                current = ""
            windows.extend(_split_long(section, size, overlap))
            continue
        candidate = f"{current}\n\n{section}".strip() if current else section
        if len(candidate) <= size:
            current = candidate
            continue
        windows.append(current.strip())
        current = section
    if current.strip():
        windows.append(current.strip())
    return windows


def _split_long(text: str, size: int, overlap: int) -> list[str]:
    """Hard-split oversized sections with overlap."""
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        pieces.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in pieces if p]
