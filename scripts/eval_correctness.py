"""Run LangSmith correctness eval against the LOGFLOWS RAG dataset."""

import argparse
import asyncio

from dotenv import load_dotenv
from langsmith import aevaluate

from app.core.config import BASE_DIR, settings
from app.core.db import close_db, init_db
from app.services.query_pipeline import run_rag_query
from evals.correctness import correctness, refusal_match

DEFAULT_DATASET_NAME = "LOGFLOWS Knowledge RAG Q&A"

for env_file in (BASE_DIR / ".env.development", BASE_DIR / ".env", BASE_DIR / ".env.example"):
    if env_file.is_file():
        load_dotenv(env_file, override=False)
        break


async def rag_target(inputs: dict) -> dict:
    """LangSmith target: one dataset row → RAG outputs."""
    result = await run_rag_query(
        tenant_id=str(inputs.get("tenant_id", "logflows-demo")),
        question=str(inputs["question"]),
        role=str(inputs.get("role", "ops")),
    )
    return {
        "answer": result.answer,
        "insufficient_evidence": result.insufficient_evidence,
        "confidence": result.confidence,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG answers vs LangSmith dataset references.")
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--experiment-prefix", default="logflows-correctness")
    parser.add_argument("--max-concurrency", type=int, default=2)
    args = parser.parse_args()

    await init_db()
    try:
        results = await aevaluate(
            rag_target,
            data=args.dataset_name,
            evaluators=[correctness, refusal_match],
            experiment_prefix=args.experiment_prefix,
            max_concurrency=args.max_concurrency,
            metadata={
                "llm_model": settings.LLM_MODEL,
                "grader_model": settings.EVAL_GRADER_MODEL,
            },
        )
        print(
            "langsmith_correctness_eval_complete",
            f"dataset={args.dataset_name}",
            f"experiment={getattr(results, 'experiment_name', args.experiment_prefix)}",
            f"grader={settings.EVAL_GRADER_MODEL}",
        )
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
