---
name: langsmith-correctness-eval
description: >-
  Write domain-agnostic LangSmith LLM-as-judge evaluators for RAG (correctness,
  relevance, groundedness, retrieval_relevance). Uses OpenRouter via the OpenAI
  SDK, not LangChain ChatOpenAI. Use when adding LangSmith evals, evaluate()/
  aevaluate() experiments, or swapping datasets for a new domain.
---

# LangSmith RAG evaluators (OpenRouter)

Each metric is a **separate module** under `evals/`. Shared OpenRouter JSON
parsing lives in `evals/grader_utils.py` only.

| Module | LangSmith key | Needs reference? | Inputs |
|--------|---------------|------------------|--------|
| `evals/correctness.py` | `correctness` | Yes | question + answer vs reference |
| `evals/relevance.py` | `relevance` | No | question + answer |
| `evals/groundedness.py` | `groundedness` | No | documents + answer |
| `evals/retrieval_relevance.py` | `retrieval_relevance` | No | question + documents |

Run all four: `make eval` → `scripts/eval.py` → `aevaluate(..., evaluators=[...])`.

## Target contract

The eval target must return at least:

```python
{
    "answer": "...",
    "documents": ["..."],  # retrieved context blocks (strings)
}
```

This repo uses `run_rag_eval()` in `app/services/query_pipeline.py`.

## New domain checklist

1. New `evals/dataset_examples.json` (questions + reference answers)
2. `make eval-dataset`
3. Keep grader modules unchanged
4. `make eval`

## Do not

- Put domain facts in grader prompts
- Use `ChatOpenAI` when the app uses OpenRouter
- Name the runner after one metric — use `scripts/eval.py` + `make eval`
