"""LLM-as-judge correctness evaluator for RAG answers vs reference answers.

Uses OpenRouter (OpenAI-compatible SDK), not LangChain ChatOpenAI.
Domain knowledge lives in the dataset; this grader is domain-agnostic.
"""

import json
import re
from typing import Annotated, TypedDict

from openai import OpenAI

from app.core.config import settings

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class CorrectnessGrade(TypedDict):
    """Grade output schema. Explanation first so the model reasons before scoring."""

    explanation: Annotated[str, ..., "Explain your reasoning for the score"]
    correct: Annotated[bool, ..., "True if the answer is correct, False otherwise."]


CORRECTNESS_INSTRUCTIONS = """You are a teacher grading a quiz. You will be given a QUESTION, the GROUND TRUTH (correct) ANSWER, and the STUDENT ANSWER. Here is the grade criteria to follow:
(1) Grade the student answers based ONLY on their factual accuracy relative to the ground truth answer. (2) Ensure that the student answer does not contain any conflicting statements.
(3) It is OK if the student answer contains more information than the ground truth answer, as long as it is factually accurate relative to the  ground truth answer.

Correctness:
A correctness value of True means that the student's answer meets all of the criteria.
A correctness value of False means that the student's answer does not meet all of the criteria.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset.

Respond with a JSON object only, using this schema:
{"explanation": "<string>", "correct": <true|false>}"""


def parse_correctness_grade(text: str) -> CorrectnessGrade:
    """Parse a JSON grade from model text (fences and extra prose allowed)."""
    stripped = text.strip()
    fenced = _JSON_FENCE.search(stripped)
    if fenced:
        stripped = fenced.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("grader response did not contain a JSON object")
    payload = json.loads(stripped[start : end + 1])
    explanation = str(payload.get("explanation", "")).strip()
    correct = payload.get("correct")
    if isinstance(correct, str):
        correct = correct.strip().lower() in {"true", "yes", "1"}
    if not isinstance(correct, bool):
        raise ValueError("grader JSON missing boolean 'correct'")
    return {"explanation": explanation, "correct": correct}


def _sync_openrouter_client() -> OpenAI:
    """Sync OpenAI SDK pointed at OpenRouter (eval graders are sync)."""
    return OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/logflows-knowledge-rag",
            "X-Title": settings.PROJECT_NAME,
        },
    )


def grade_correctness(question: str, student_answer: str, ground_truth: str) -> CorrectnessGrade:
    """Ask the OpenRouter chat model to score student vs ground-truth answers."""
    client = _sync_openrouter_client()
    answers = (
        f"QUESTION: {question}\n"
        f"GROUND TRUTH ANSWER: {ground_truth}\n"
        f"STUDENT ANSWER: {student_answer}"
    )
    create_kwargs = {
        "model": settings.EVAL_GRADER_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": CORRECTNESS_INSTRUCTIONS},
            {"role": "user", "content": answers},
        ],
    }
    try:
        completion = client.chat.completions.create(
            **create_kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        completion = client.chat.completions.create(**create_kwargs)
    content = (completion.choices[0].message.content or "").strip()
    return parse_correctness_grade(content)


def correctness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """LangSmith evaluator: RAG answer accuracy vs the dataset reference."""
    question = str(inputs.get("question", ""))
    student_answer = str(outputs.get("answer", ""))
    ground_truth = str(reference_outputs.get("answer", ""))
    grade = grade_correctness(question, student_answer, ground_truth)
    return {
        "key": "correctness",
        "score": 1.0 if grade["correct"] else 0.0,
        "comment": grade["explanation"],
    }


def refusal_match(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Cheap check: predicted refusal flag matches the reference (no extra LLM call)."""
    del inputs
    expected = bool(reference_outputs.get("insufficient_evidence", False))
    predicted = bool(outputs.get("insufficient_evidence", False))
    return {
        "key": "refusal_match",
        "score": 1.0 if expected == predicted else 0.0,
        "comment": f"expected_insufficient={expected} predicted_insufficient={predicted}",
    }
