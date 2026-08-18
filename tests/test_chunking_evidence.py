"""Chunking and evidence-gate unit tests."""

from app.chunking import chunk_text
from app.evidence import confidence_label, is_insufficient


def test_chunk_keeps_heading_blocks() -> None:
    """SOP-style headings should produce more than one chunk on long text."""
    text = "# A\n" + ("step one. " * 80) + "\n\n# B\n" + ("step two. " * 80)
    chunks = chunk_text("sop-001", "Cold Chain SOP", text, chunk_size=200, overlap=20)
    assert len(chunks) >= 2
    assert chunks[0]["chunk_id"] == "sop-001:0"
    assert "Cold Chain SOP" in chunks[0]["content"]


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
