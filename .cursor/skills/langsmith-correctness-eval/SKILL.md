---
name: langsmith-correctness-eval
description: >-
  Write a domain-agnostic LangSmith LLM-as-judge correctness evaluator that
  scores a RAG (or chat) student answer against a reference answer. Uses
  OpenRouter via the OpenAI SDK, not LangChain ChatOpenAI. Use when adding
  LangSmith evals, correctness graders, evaluate()/aevaluate() experiments,
  or when swapping datasets for a new domain while keeping the same scoring
  criteria.
---

# LangSmith correctness eval (OpenRouter)

Correctness scoring is **universal**. Domain facts live only in the dataset
(`inputs.question` + `outputs.answer`). Do not put SOP/policy text in the
grader prompt.

This repo implements the pattern in:

- `evals/correctness.py` — grader + LangSmith evaluators
- `scripts/eval_correctness.py` — `aevaluate` runner
- `evals/dataset_examples.json` — LOGFLOWS domain examples

## Dataset contract

Each example must use this shape so one evaluator works across domains:

```json
{
  "inputs": { "question": "..." },
  "outputs": { "answer": "..." }
}
```

Extra input fields (`tenant_id`, `role`, ...) are allowed. The grader only
reads `question` and `answer`. Optional `insufficient_evidence` is scored by
`refusal_match` (no extra LLM call).

## Grader (no ChatOpenAI)

Use the OpenAI SDK pointed at OpenRouter. Ask for JSON. Put `explanation`
before `correct` so the model reasons first.

Copy `CORRECTNESS_INSTRUCTIONS` and `correctness()` from `evals/correctness.py`.
Parse JSON defensively: strip fences, then first `{` … last `}`. If
`response_format=json_object` fails on a reasoning model, retry without it.

## Target + experiment

`scripts/eval_correctness.py` calls `run_rag_query` in-process and runs:

```bash
make eval-dataset      # once: upload examples
make eval-correctness  # experiment vs LangSmith dataset
```

Env: `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `OPENROUTER_API_KEY`,
`EVAL_GRADER_MODEL` (defaults to the app chat model via OpenRouter).

## New domain checklist

1. Write a new `dataset_examples.json` for that corpus
2. Upload with `scripts/create_langsmith_dataset.py --dataset-name "..."`
3. Keep `evals/correctness.py` unchanged
4. Point `aevaluate(..., data="<new dataset name>")` at the new dataset
5. Optional extra evaluators (refusal, citations) stay separate from the judge prompt

## Do not

- Put domain facts in `CORRECTNESS_INSTRUCTIONS`
- Use `langchain_openai.ChatOpenAI` when the app is on OpenRouter
- Score on style, length, or citation format in this judge — only factual accuracy vs ground truth
