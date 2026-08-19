"""Tests for retrieval context formatting and citation partitioning."""

from app.services.context import build_llm_context_blocks, format_context_block, partition_retrieval_hits


def test_partition_retrieval_hits_splits_primary_from_section_siblings() -> None:
    """Direct hits become citations; expanded siblings stay LLM-only context."""
    hits = [
        {
            "document_id": "sop-001",
            "chunk_id": "logflows-demo:sop-001:3",
            "score": 0.55,
            "is_primary_hit": True,
            "title": "Cold Chain SOP",
            "header_path": "Cold Chain SOP > Delay procedure",
            "metadata": {"h2": "Delay procedure"},
            "content": "Notify QC within 10 minutes.",
        },
        {
            "document_id": "sop-001",
            "chunk_id": "logflows-demo:sop-001:4",
            "score": 0.55,
            "is_primary_hit": False,
            "title": "Cold Chain SOP",
            "header_path": "Cold Chain SOP > Delay procedure",
            "metadata": {"h2": "Delay procedure"},
            "content": "Record trailer temperature on the delay form.",
        },
    ]

    primary_hits, context_hits = partition_retrieval_hits(hits)

    assert len(primary_hits) == 1
    assert primary_hits[0]["chunk_id"] == "logflows-demo:sop-001:3"
    assert len(context_hits) == 2


def test_format_context_block_includes_metadata_and_role_label() -> None:
    """LLM blocks expose title, header_path, hierarchy metadata, score, and body."""
    block = format_context_block(
        {
            "document_id": "sop-001",
            "chunk_id": "logflows-demo:sop-001:3",
            "score": 0.5452,
            "is_primary_hit": True,
            "title": "Cold Chain SOP",
            "header_path": "Cold Chain SOP > Delay procedure",
            "metadata": {
                "document_title": "Cold Chain SOP",
                "h1": "Cold Chain SOP (SOP-001)",
                "h2": "Delay procedure",
            },
            "content": "Notify QC within 10 minutes.",
        }
    )

    assert "PRIMARY SOURCE" in block
    assert "document_id: sop-001" in block
    assert "header_path: Cold Chain SOP > Delay procedure" in block
    assert "h2: Delay procedure" in block
    assert "retrieval_score: 0.5452" in block
    assert "Notify QC within 10 minutes." in block


def test_build_llm_context_blocks_marks_section_siblings() -> None:
    """Section-expanded rows are labeled SECTION CONTEXT for the LLM."""
    blocks = build_llm_context_blocks(
        [
            {
                "document_id": "sop-001",
                "chunk_id": "a",
                "score": 0.5,
                "is_primary_hit": False,
                "title": "Cold Chain SOP",
                "header_path": "x",
                "metadata": {},
                "content": "Sibling step.",
            }
        ]
    )

    assert blocks[0].startswith("--- SECTION CONTEXT ---")
