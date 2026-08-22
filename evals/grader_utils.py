"""Shared helpers for OpenRouter LLM-as-judge eval graders."""

import json
import re

from openai import OpenAI

from app.core.config import settings

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def sync_openrouter_client() -> OpenAI:
    """Sync OpenAI SDK pointed at OpenRouter (eval graders are sync)."""
    return OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/logflows-knowledge-rag",
            "X-Title": settings.PROJECT_NAME,
        },
    )


def parse_json_bool_grade(text: str, bool_key: str) -> tuple[str, bool]:
    """Parse explanation + boolean score from grader JSON (fences allowed)."""
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
    value = payload.get(bool_key)
    if isinstance(value, str):
        value = value.strip().lower() in {"true", "yes", "1"}
    if not isinstance(value, bool):
        raise ValueError(f"grader JSON missing boolean '{bool_key}'")
    return explanation, value


def run_json_grader(system_instructions: str, user_content: str) -> str:
    """Call the OpenRouter chat model and return raw assistant text."""
    client = sync_openrouter_client()
    create_kwargs = {
        "model": settings.EVAL_GRADER_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": user_content},
        ],
    }
    try:
        completion = client.chat.completions.create(
            **create_kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        completion = client.chat.completions.create(**create_kwargs)
    return (completion.choices[0].message.content or "").strip()
