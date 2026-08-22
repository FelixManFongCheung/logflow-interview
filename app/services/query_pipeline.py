"""RAG query pipeline without HTTP wrappers, used by the API and LangSmith evals."""

from app.schema.schemas import Citation, QueryResponse
from app.services.context import build_llm_context_blocks, filter_context_hits, partition_retrieval_hits
from app.services.evidence import confidence_label, filter_primary_hits, is_insufficient
from app.services.llm import generate_answer
from app.services.retriever import hybrid_search


class RetrievalFailed(Exception):
    """Hybrid search or embedding failed."""


class GenerationFailed(Exception):
    """LLM generation failed after retrieval succeeded."""


def _normalize_chunk_metadata(raw: object) -> dict[str, str]:
    """Coerce JSONB metadata from Postgres into citation-safe string values."""
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def _refusal_payload(answer: str) -> QueryResponse:
    return QueryResponse(
        answer=answer,
        citations=[],
        confidence="low",
        insufficient_evidence=True,
    )


async def run_rag_query(tenant_id: str, question: str, role: str = "ops") -> QueryResponse:
    """Retrieve tenant-scoped chunks; answer or refuse based on evidence scores."""
    try:
        hits = await hybrid_search(tenant_id, question, role=role)
    except Exception as exc:
        raise RetrievalFailed(str(exc)) from exc

    primary_hits, context_hits = partition_retrieval_hits(hits)
    all_primary_scores = [float(hit["score"]) for hit in primary_hits]

    if is_insufficient(all_primary_scores):
        return _refusal_payload("Not enough indexed evidence to answer this question.")

    kept_primaries = filter_primary_hits(primary_hits)
    if not kept_primaries:
        return _refusal_payload("Not enough indexed evidence to answer this question.")

    scores = [float(hit["score"]) for hit in kept_primaries]
    citations = [
        Citation(
            document_id=hit["document_id"],
            chunk_id=hit["chunk_id"],
            score=round(float(hit["score"]), 4),
            title=hit.get("title"),
            header_path=hit.get("header_path"),
            metadata=_normalize_chunk_metadata(hit.get("metadata")),
        )
        for hit in kept_primaries
    ]
    confidence = confidence_label(scores)
    context_hits = filter_context_hits(kept_primaries, context_hits)
    context_blocks = build_llm_context_blocks(context_hits)

    try:
        answer = await generate_answer(question, context_blocks)
    except Exception as exc:
        raise GenerationFailed(str(exc)) from exc

    if answer.strip().upper().startswith("INSUFFICIENT_EVIDENCE"):
        return _refusal_payload("Retrieved sources do not contain a complete answer.")

    return QueryResponse(
        answer=answer,
        citations=citations,
        confidence=confidence,
        insufficient_evidence=False,
    )
