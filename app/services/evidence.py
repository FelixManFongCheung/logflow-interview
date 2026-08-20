"""Evidence gating, elbow cutoff, and confidence labels from retrieval scores."""

from typing import Any, Literal

from app.core.config import settings


def compute_elbow_cutoff(scores: list[float]) -> float | None:
    """Return the lowest score in the top cluster before the largest consecutive drop.

    Sorts primary-hit scores descending, finds the sharpest gap between neighbours,
    and returns the score at the cliff edge (last kept item in the upper cluster).
    Returns None when there are fewer than two scores or the gap is too small to trust.
    """
    if len(scores) < 2:
        return None

    sorted_scores = sorted(scores, reverse=True)
    max_gap = 0.0
    max_gap_index = 0

    for index in range(len(sorted_scores) - 1):
        gap = sorted_scores[index] - sorted_scores[index + 1]
        if gap > max_gap:
            max_gap = gap
            max_gap_index = index

    top_score = sorted_scores[0]
    if max_gap < settings.ELBOW_MIN_GAP:
        return None
    if top_score > 0 and (max_gap / top_score) < settings.ELBOW_MIN_RELATIVE_GAP:
        return None

    return sorted_scores[max_gap_index]


def effective_evidence_threshold(scores: list[float]) -> float:
    """Combine absolute floor with per-query elbow cutoff when a cliff is detected."""
    floor = settings.EVIDENCE_THRESHOLD
    if not settings.USE_ELBOW_GATE:
        return floor

    elbow_cutoff = compute_elbow_cutoff(scores)
    if elbow_cutoff is None:
        return floor
    return max(floor, elbow_cutoff)


def filter_primary_hits(primary_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep primary hits at or above the effective threshold, capped at RETRIEVE_K."""
    if not primary_hits:
        return []

    scores = [float(hit["score"]) for hit in primary_hits]
    if max(scores) < settings.EVIDENCE_THRESHOLD:
        return []

    cutoff = effective_evidence_threshold(scores)
    kept = [hit for hit in primary_hits if float(hit["score"]) >= cutoff]
    kept.sort(key=lambda hit: float(hit["score"]), reverse=True)
    return kept[: settings.RETRIEVE_K]


def is_insufficient(scores: list[float]) -> bool:
    """True when nothing useful was retrieved (absolute floor on raw primary scores)."""
    if not scores:
        return True
    return max(scores) < settings.EVIDENCE_THRESHOLD


def confidence_label(scores: list[float]) -> Literal["high", "medium", "low"]:
    """Map kept primary scores to high/medium/low."""
    if not scores:
        return "low"
    top = max(scores)
    if top >= settings.HIGH_CONFIDENCE_THRESHOLD and len(scores) >= 2:
        return "high"
    if top >= settings.EVIDENCE_THRESHOLD:
        return "medium"
    return "low"
