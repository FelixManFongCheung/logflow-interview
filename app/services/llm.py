"""OpenRouter clients: Qwen embeddings and a separate cheap/free chat model."""

from openai import AsyncOpenAI

from app.core.config import settings

_embedding_client: AsyncOpenAI | None = None
_chat_client: AsyncOpenAI | None = None

def _make_openrouter_client() -> AsyncOpenAI:
    """OpenAI SDK pointed at OpenRouter (same REST shape as /api/v1/chat/completions)."""
    return AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/logflows-knowledge-rag",
            "X-Title": settings.PROJECT_NAME,
        },
    )


def get_embedding_client() -> AsyncOpenAI:
    """Client for POST /embeddings (qwen/qwen3-embedding-4b)."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = _make_openrouter_client()
    return _embedding_client


def get_chat_client() -> AsyncOpenAI:
    """Client for POST /chat/completions (free/cheap LLM, not the embedding model)."""
    global _chat_client
    if _chat_client is None:
        _chat_client = _make_openrouter_client()
    return _chat_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings. Empty input returns an empty list."""
    if not texts:
        return []
    client = get_embedding_client()
    create_kwargs: dict = {
        "model": settings.EMBEDDING_MODEL,
        "input": texts,
        "encoding_format": "float",
    }
    if settings.EMBEDDING_DIMENSIONS:
        create_kwargs["dimensions"] = settings.EMBEDDING_DIMENSIONS
    response = await client.embeddings.create(**create_kwargs)
    return [item.embedding for item in response.data]


async def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    vectors = await embed_texts([text])
    return vectors[0]


async def generate_answer(question: str, context_blocks: list[str]) -> str:
    """Generate a grounded answer or an explicit insufficient-evidence line."""
    client = get_chat_client()
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
