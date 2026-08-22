"""Run LangSmith RAG eval with all LLM-as-judge metrics."""

import argparse
import asyncio

from dotenv import load_dotenv
from langsmith import aevaluate

from app.core.config import BASE_DIR, settings
from app.core.db import close_db, init_db
from app.services.query_pipeline import run_rag_eval
from evals.correctness import correctness
from evals.groundedness import groundedness
from evals.relevance import relevance
from evals.retrieval_relevance import retrieval_relevance

DEFAULT_DATASET_NAME = "LOGFLOWS Knowledge RAG Q&A"
DEFAULT_EVALUATORS = [correctness, groundedness, relevance, retrieval_relevance]

for env_file in (BASE_DIR / ".env.development", BASE_DIR / ".env", BASE_DIR / ".env.example"):
    if env_file.is_file():
        load_dotenv(env_file, override=False)
        break


async def rag_target(inputs: dict) -> dict:
    """LangSmith target: one dataset row → RAG outputs including retrieved context."""
    result = await run_rag_eval(
        tenant_id=str(inputs.get("tenant_id", "logflows-demo")),
        question=str(inputs["question"]),
        role=str(inputs.get("role", "ops")),
    )
    response = result.response
    return {
        "answer": response.answer,
        "insufficient_evidence": response.insufficient_evidence,
        "confidence": response.confidence,
        "documents": result.documents,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate RAG with LangSmith (correctness, groundedness, relevance, retrieval_relevance)."
    )
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--experiment-prefix", default="logflows-rag-eval")
    parser.add_argument("--max-concurrency", type=int, default=2)
    args = parser.parse_args()

    await init_db()
    try:
        results = await aevaluate(
            rag_target,
            data=args.dataset_name,
            evaluators=DEFAULT_EVALUATORS,
            experiment_prefix=args.experiment_prefix,
            max_concurrency=args.max_concurrency,
            metadata={
                "llm_model": settings.LLM_MODEL,
                "grader_model": settings.EVAL_GRADER_MODEL,
            },
        )
        print(
            "langsmith_rag_eval_complete",
            f"dataset={args.dataset_name}",
            f"experiment={getattr(results, 'experiment_name', args.experiment_prefix)}",
            f"evaluators={[fn.__name__ for fn in DEFAULT_EVALUATORS]}",
            f"grader={settings.EVAL_GRADER_MODEL}",
        )
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
