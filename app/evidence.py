"""Evidence gating and confidence labels from retrieval scores."""

from typing import Literal

from app.core.config import settings


def is_insufficient(scores: list[float]) -> bool:
    """True when nothing useful was retrieved."""
    if not scores:
        return True
    return max(scores) < settings.EVIDENCE_THRESHOLD


def confidence_label(scores: list[float]) -> Literal["high", "medium", "low"]:
    """Map top hybrid score to high/medium/low."""
    if not scores:
        return "low"
    top = max(scores)
    if top >= settings.HIGH_CONFIDENCE_THRESHOLD and len(scores) >= 2:
        return "high"
    if top >= settings.EVIDENCE_THRESHOLD:
        return "medium"
    return "low"
