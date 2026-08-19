"""Format retrieval hits for LLM context vs API citations."""

from typing import Any


def partition_retrieval_hits(hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split direct retrieval hits from section-expanded sibling context.

    Returns:
        primary_hits — top-k direct matches (citations, evidence scoring).
        context_hits — all hits including section siblings (LLM prompt only).
    """
    primary_hits = [hit for hit in hits if hit.get("is_primary_hit", True)]
    return primary_hits, hits


def format_context_block(hit: dict[str, Any]) -> str:
    """Render one retrieval row with document topic, hierarchy, metadata, and body."""
    is_primary = hit.get("is_primary_hit", True)
    role_label = "PRIMARY SOURCE" if is_primary else "SECTION CONTEXT"
    metadata = _coerce_metadata(hit.get("metadata"))

    lines = [
        f"--- {role_label} ---",
        f"document_id: {hit.get('document_id', '')}",
        f"chunk_id: {hit.get('chunk_id', '')}",
        f"title: {hit.get('title') or metadata.get('document_title', 'n/a')}",
        f"header_path: {hit.get('header_path') or 'n/a'}",
        f"retrieval_score: {float(hit.get('score', 0.0)):.4f}",
    ]

    for key in ("document_title", "h1", "h2", "h3"):
        value = metadata.get(key)
        if value:
            lines.append(f"{key}: {value}")

    lines.append(f"body:\n{hit.get('content', '').strip()}")
    return "\n".join(lines)


def build_llm_context_blocks(hits: list[dict[str, Any]]) -> list[str]:
    """Build ordered context blocks for the LLM from all retrieval rows."""
    return [format_context_block(hit) for hit in hits]


def _coerce_metadata(raw: object) -> dict[str, str]:
    """Normalize Postgres JSONB metadata into string key/value pairs."""
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}
