"""Unit tests for LLM-as-judge grade parsers."""

import pytest

from evals.correctness import parse_correctness_grade, refusal_match
from evals.groundedness import parse_grounded_grade
from evals.relevance import parse_relevance_grade
from evals.retrieval_relevance import parse_retrieval_relevance_grade
from evals.document_utils import format_documents


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


def test_parse_relevance_grade_from_plain_json() -> None:
    grade = parse_relevance_grade('{"explanation": "On topic.", "relevant": true}')
    assert grade["relevant"] is True


def test_parse_relevance_grade_from_fenced_json() -> None:
    grade = parse_relevance_grade(
        '```json\n{"explanation": "Off topic.", "relevant": false}\n```'
    )
    assert grade["relevant"] is False


def test_parse_retrieval_relevance_grade_from_plain_json() -> None:
    grade = parse_retrieval_relevance_grade('{"explanation": "Related topics.", "relevant": true}')
    assert grade["relevant"] is True


def test_parse_grounded_grade_from_plain_json() -> None:
    grade = parse_grounded_grade('{"explanation": "Supported by facts.", "grounded": true}')
    assert grade["grounded"] is True


def test_format_documents_joins_strings() -> None:
    assert "chunk-a" in format_documents(["chunk-a", "chunk-b"])


def test_format_documents_empty() -> None:
    assert format_documents([]) == "(no documents retrieved)"


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
