"""LLM-as-judge relevance evaluator: does the answer address the question?

Uses OpenRouter (OpenAI-compatible SDK), not LangChain ChatOpenAI.
Domain-agnostic — no reference answer required.
"""

from typing import Annotated, TypedDict

from evals.grader_utils import parse_json_bool_grade, run_json_grader

RELEVANCE_INSTRUCTIONS = """You are a teacher grading a quiz. You will be given a QUESTION and a STUDENT ANSWER. Here is the grade criteria to follow:
(1) Ensure the STUDENT ANSWER is concise and relevant to the QUESTION
(2) Ensure the STUDENT ANSWER helps to answer the QUESTION

Relevance:
A relevance value of True means that the student's answer meets all of the criteria.
A relevance value of False means that the student's answer does not meet all of the criteria.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset.

Respond with a JSON object only, using this schema:
{"explanation": "<string>", "relevant": <true|false>}"""


class RelevanceGrade(TypedDict):
    """Grade output schema. Explanation first so the model reasons before scoring."""

    explanation: Annotated[str, ..., "Explain your reasoning for the score"]
    relevant: Annotated[bool, ..., "Provide the score on whether the answer addresses the question"]


def parse_relevance_grade(text: str) -> RelevanceGrade:
    """Parse a JSON relevance grade from model text."""
    explanation, relevant = parse_json_bool_grade(text, "relevant")
    return {"explanation": explanation, "relevant": relevant}


def grade_relevance(question: str, student_answer: str) -> RelevanceGrade:
    """Ask the OpenRouter chat model whether the answer is relevant to the question."""
    prompt = f"QUESTION: {question}\nSTUDENT ANSWER: {student_answer}"
    content = run_json_grader(RELEVANCE_INSTRUCTIONS, prompt)
    return parse_relevance_grade(content)


def relevance(inputs: dict, outputs: dict) -> dict:
    """LangSmith evaluator: RAG answer helpfulness / on-topic vs the question."""
    question = str(inputs.get("question", ""))
    student_answer = str(outputs.get("answer", ""))
    grade = grade_relevance(question, student_answer)
    return {
        "key": "relevance",
        "score": 1.0 if grade["relevant"] else 0.0,
        "comment": grade["explanation"],
    }
