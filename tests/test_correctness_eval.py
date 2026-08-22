"""Unit tests for the domain-agnostic correctness grade parser."""

import pytest

from evals.correctness import parse_correctness_grade, refusal_match


def test_parse_correctness_grade_from_plain_json() -> None:
    grade = parse_correctness_grade('{"explanation": "Matches the facts.", "correct": true}')
    assert grade["correct"] is True
    assert "facts" in grade["explanation"]


def test_parse_correctness_grade_from_fenced_json() -> None:
    grade = parse_correctness_grade(
        'Here is the grade:\n```json\n{"explanation": "Conflicts with ground truth.", "correct": false}\n```'
    )
    assert grade["correct"] is False


def test_parse_correctness_grade_rejects_missing_json() -> None:
    with pytest.raises(ValueError):
        parse_correctness_grade("the student is correct")


def test_refusal_match_detects_mismatch() -> None:
    result = refusal_match(
        inputs={"question": "What is Q4 revenue?"},
        outputs={"answer": "42 million", "insufficient_evidence": False},
        reference_outputs={"answer": "Not enough indexed evidence.", "insufficient_evidence": True},
    )
    assert result["key"] == "refusal_match"
    assert result["score"] == 0.0


def test_refusal_match_passes_when_flags_agree() -> None:
    result = refusal_match(
        inputs={"question": "What is Q4 revenue?"},
        outputs={"answer": "Not enough indexed evidence.", "insufficient_evidence": True},
        reference_outputs={"answer": "Not enough indexed evidence.", "insufficient_evidence": True},
    )
    assert result["score"] == 1.0
