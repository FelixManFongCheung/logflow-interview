"""Document-aware hierarchical chunking via LangChain splitters."""

from __future__ import annotations

import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, TokenTextSplitter

from app.core.config import settings

_HEADER_LEVELS = [("#", "h1"), ("##", "h2"), ("###", "h3")]
_HEADER_KEYS = ("h1", "h2", "h3")
_TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")


def chunk_text(
    document_id: str,
    title: str,
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
    chunk_size_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[dict]:
    """Split markdown by headers, then by token limit when a section is too long."""
    cleaned = text.strip()
    if not cleaned:
        return []

    size_tokens = _resolve_token_budget(chunk_size_tokens, chunk_size, settings.CHUNK_SIZE_TOKENS)
    overlap_tok = _resolve_token_budget(overlap_tokens, overlap, settings.CHUNK_OVERLAP_TOKENS)

    header_blocks = _split_by_headers(cleaned)
    leaf_docs = _split_oversized_blocks(header_blocks, size_tokens, overlap_tok)

    chunks: list[dict] = []
    for index, doc in enumerate(leaf_docs):
        metadata = _inherit_metadata(doc, document_id=document_id, title=title)
        content = _build_chunk_content(title=title, metadata=metadata, body=doc.page_content)
        chunks.append(
            {
                "chunk_id": f"{document_id}:{index}",
                "document_id": document_id,
                "title": title,
                "content": content,
                "chunk_index": index,
                "metadata": metadata,
            }
        )
    return chunks


def _resolve_token_budget(
    token_value: int | None,
    char_value: int | None,
    default_tokens: int,
) -> int:
    """Prefer explicit token limits; fall back to char/4 conversion."""
    if token_value is not None:
        return max(token_value, 1)
    if char_value is not None:
        return max(char_value // 4, 1)
    return max(default_tokens, 1)


def _split_by_headers(text: str) -> list[Document]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADER_LEVELS,
        strip_headers=True,
    )
    return splitter.split_text(text)


def _split_oversized_blocks(
    blocks: list[Document],
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> list[Document]:
    token_splitter = TokenTextSplitter(
        chunk_size=chunk_size_tokens,
        chunk_overlap=overlap_tokens,
    )
    leaves: list[Document] = []
    for block in blocks:
        if _token_count(block.page_content) <= chunk_size_tokens:
            leaves.append(block)
            continue
        leaves.extend(token_splitter.split_documents([block]))
    return leaves


def _inherit_metadata(doc: Document, document_id: str, title: str) -> dict[str, str]:
    metadata = {key: str(doc.metadata[key]) for key in _HEADER_KEYS if doc.metadata.get(key)}
    metadata["document_id"] = document_id
    metadata["document_title"] = title
    header_path = [metadata[key] for key in _HEADER_KEYS if metadata.get(key)]
    if header_path:
        metadata["header_path"] = " > ".join(header_path)
    return metadata


def _build_chunk_content(title: str, metadata: dict[str, str], body: str) -> str:
    header_lines = [f"{'#' * int(key[1])} {metadata[key]}" for key in _HEADER_KEYS if metadata.get(key)]
    parts = [title]
    if header_lines:
        parts.append("\n".join(header_lines))
    if body.strip():
        parts.append(body.strip())
    return "\n\n".join(parts)


def _token_count(text: str) -> int:
    """Count tokens using the same encoding family as TokenTextSplitter."""
    return len(_TOKEN_ENCODER.encode(text))
