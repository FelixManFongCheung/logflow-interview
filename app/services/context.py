"""Format retrieval hits for LLM context vs API citations."""

from typing import Any


def partition_retrieval_hits(hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (primary hits for citations/scoring, all hits for LLM context)."""
    primary_hits = [hit for hit in hits if hit.get("is_primary_hit", True)]
    return primary_hits, hits


def filter_context_hits(
    kept_primaries: list[dict[str, Any]],
    all_hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Limit LLM context to elbow-kept primaries and their section siblings."""
    if not kept_primaries:
        return []

    kept_chunk_ids = {hit["chunk_id"] for hit in kept_primaries}
    kept_sections = {(hit.get("document_id"), hit.get("header_path")) for hit in kept_primaries}

    filtered: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    for hit in all_hits:
        chunk_id = hit["chunk_id"]
        if chunk_id in seen_chunk_ids:
            continue

        if hit.get("is_primary_hit", True):
            if chunk_id in kept_chunk_ids:
                filtered.append(hit)
                seen_chunk_ids.add(chunk_id)
            continue

        section_key = (hit.get("document_id"), hit.get("header_path"))
        if section_key in kept_sections:
            filtered.append(hit)
            seen_chunk_ids.add(chunk_id)

    return filtered


def format_context_block(hit: dict[str, Any]) -> str:
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
    return [format_context_block(hit) for hit in hits]


def _coerce_metadata(raw: object) -> dict[str, str]:
    """Normalize Postgres JSONB metadata into string key/value pairs."""
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}
