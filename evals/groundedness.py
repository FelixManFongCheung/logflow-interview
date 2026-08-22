"""LLM-as-judge groundedness: is the answer supported by retrieved facts?

Uses OpenRouter (OpenAI-compatible SDK), not LangChain ChatOpenAI.
"""

from typing import Annotated, TypedDict

from evals.document_utils import format_documents
from evals.grader_utils import parse_json_bool_grade, run_json_grader

GROUNDED_INSTRUCTIONS = """You are a teacher grading a quiz. You will be given FACTS and a STUDENT ANSWER. Here is the grade criteria to follow:
(1) Ensure the STUDENT ANSWER is grounded in the FACTS. (2) Ensure the STUDENT ANSWER does not contain "hallucinated" information outside the scope of the FACTS.

Grounded:
A grounded value of True means that the student's answer meets all of the criteria.
A grounded value of False means that the student's answer does not meet all of the criteria.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset.

Respond with a JSON object only, using this schema:
{"explanation": "<string>", "grounded": <true|false>}"""


class GroundedGrade(TypedDict):
    explanation: Annotated[str, ..., "Explain your reasoning for the score"]
    grounded: Annotated[bool, ..., "Provide the score on if the answer hallucinates from the documents"]


def parse_grounded_grade(text: str) -> GroundedGrade:
    explanation, grounded = parse_json_bool_grade(text, "grounded")
    return {"explanation": explanation, "grounded": grounded}


def grade_groundedness(documents: list[str], student_answer: str) -> GroundedGrade:
    doc_string = format_documents(documents)
    prompt = f"FACTS: {doc_string}\nSTUDENT ANSWER: {student_answer}"
    content = run_json_grader(GROUNDED_INSTRUCTIONS, prompt)
    return parse_grounded_grade(content)


def groundedness(inputs: dict, outputs: dict) -> dict:
    """LangSmith evaluator: answer grounded in retrieved documents (no reference answer)."""
    del inputs
    documents = outputs.get("documents") or []
    student_answer = str(outputs.get("answer", ""))
    grade = grade_groundedness(documents, student_answer)
    return {
        "key": "groundedness",
        "score": 1.0 if grade["grounded"] else 0.0,
        "comment": grade["explanation"],
    }
