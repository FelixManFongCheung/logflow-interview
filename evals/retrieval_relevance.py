"""LLM-as-judge retrieval relevance: are retrieved documents related to the question?

Uses OpenRouter (OpenAI-compatible SDK), not LangChain ChatOpenAI.
"""

from typing import Annotated, TypedDict

from evals.document_utils import format_documents
from evals.grader_utils import parse_json_bool_grade, run_json_grader

RETRIEVAL_RELEVANCE_INSTRUCTIONS = """You are a teacher grading a quiz. You will be given a QUESTION and a set of FACTS provided by the student. Here is the grade criteria to follow:
(1) You goal is to identify FACTS that are completely unrelated to the QUESTION
(2) If the facts contain ANY keywords or semantic meaning related to the question, consider them relevant
(3) It is OK if the facts have SOME information that is unrelated to the question as long as (2) is met

Relevance:
A relevance value of True means that the FACTS contain ANY keywords or semantic meaning related to the QUESTION and are therefore relevant.
A relevance value of False means that the FACTS are completely unrelated to the QUESTION.

Explain your reasoning in a step-by-step manner to ensure your reasoning and conclusion are correct. Avoid simply stating the correct answer at the outset.

Respond with a JSON object only, using this schema:
{"explanation": "<string>", "relevant": <true|false>}"""


class RetrievalRelevanceGrade(TypedDict):
    explanation: Annotated[str, ..., "Explain your reasoning for the score"]
    relevant: Annotated[
        bool,
        ...,
        "True if the retrieved documents are relevant to the question, False otherwise",
    ]


def parse_retrieval_relevance_grade(text: str) -> RetrievalRelevanceGrade:
    explanation, relevant = parse_json_bool_grade(text, "relevant")
    return {"explanation": explanation, "relevant": relevant}


def grade_retrieval_relevance(question: str, documents: list[str]) -> RetrievalRelevanceGrade:
    doc_string = format_documents(documents)
    prompt = f"FACTS: {doc_string}\nQUESTION: {question}"
    content = run_json_grader(RETRIEVAL_RELEVANCE_INSTRUCTIONS, prompt)
    return parse_retrieval_relevance_grade(content)


def retrieval_relevance(inputs: dict, outputs: dict) -> dict:
    """LangSmith evaluator: retrieved documents relevant to the question."""
    question = str(inputs.get("question", ""))
    documents = outputs.get("documents") or []
    grade = grade_retrieval_relevance(question, documents)
    return {
        "key": "retrieval_relevance",
        "score": 1.0 if grade["relevant"] else 0.0,
        "comment": grade["explanation"],
    }
