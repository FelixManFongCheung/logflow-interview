"""Chunking and evidence-gate unit tests."""

from app.services.chunking import chunk_text
from app.services.evidence import confidence_label, is_insufficient


def test_chunk_keeps_heading_blocks() -> None:
    """SOP-style headings should produce more than one chunk on long text."""
    text = "# A\n" + ("step one. " * 80) + "\n\n# B\n" + ("step two. " * 80)
    chunks = chunk_text("sop-001", "Cold Chain SOP", text, chunk_size=200, overlap=20)
    assert len(chunks) >= 2
    assert chunks[0]["chunk_id"] == "sop-001:0"
    assert "Cold Chain SOP" in chunks[0]["content"]


def test_hierarchical_metadata_inherits_parent_headers() -> None:
    """Child chunks should carry header breadcrumbs in metadata and content."""
    text = "# Root\n\n## Section\n\nBody text."
    chunks = chunk_text("sop-002", "Receiving SOP", text)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["h1"] == "Root"
    assert chunks[0]["metadata"]["h2"] == "Section"
    assert chunks[0]["metadata"]["header_path"] == "Root > Section"
    assert "## Section" in chunks[0]["content"]


def test_table_section_stays_intact_when_under_token_limit() -> None:
    """Markdown tables should not be row-split when the section fits."""
    text = (
        "# SOP\n\n## Allowed temperature band\n\n"
        "| Product class | Min | Max |\n|---|---|---|\n| Chilled | 2 | 8 |\n\n"
        "Logger readings required."
    )
    chunks = chunk_text("sop-001", "Cold Chain SOP", text)
    table_chunks = [chunk for chunk in chunks if "| Chilled | 2 | 8 |" in chunk["content"]]
    assert len(table_chunks) == 1


def test_empty_text_yields_no_chunks() -> None:
    """Whitespace-only documents must not be indexed."""
    assert chunk_text("x", "t", "   ") == []


def test_insufficient_evidence_threshold() -> None:
    """Low or empty scores trigger refusal."""
    assert is_insufficient([])
    assert is_insufficient([0.05, 0.10])
    assert not is_insufficient([0.50])


def test_confidence_labels() -> None:
    """Confidence follows top score and hit count."""
    assert confidence_label([]) == "low"
    assert confidence_label([0.50, 0.48]) == "high"
    assert confidence_label([0.30]) == "medium"
