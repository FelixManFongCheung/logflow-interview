"""OpenAI-compatible embedding and chat clients."""

from openai import AsyncOpenAI

from app.core.config import settings

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Lazy OpenAI client (swap base_url for Azure/Qwen-compatible APIs)."""
    global _client
    if _client is None:
        kwargs: dict = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
        _client = AsyncOpenAI(**kwargs)
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings. Empty input returns an empty list."""
    if not texts:
        return []
    client = get_client()
    response = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


async def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    vectors = await embed_texts([text])
    return vectors[0]


async def generate_answer(question: str, context_blocks: list[str]) -> str:
    """Generate a grounded answer or an explicit insufficient-evidence line."""
    client = get_client()
    context = "\n\n".join(context_blocks) if context_blocks else "(no retrieved context)"
    completion = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a logistics operations assistant for LOGFLOWS. "
                    "Answer using ONLY the provided source chunks. "
                    "If the chunks do not contain the answer, reply exactly: "
                    "INSUFFICIENT_EVIDENCE. "
                    "Do not invent SOP ids, phone numbers, temperatures, or SLAs. "
                    "Be concise and cite document ids inline like [sop-001] when you use them."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nSource chunks:\n{context}",
            },
        ],
    )
    return (completion.choices[0].message.content or "").strip()
