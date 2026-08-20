"""Query route."""

from fastapi import APIRouter, Response

from app.schema.responses import CorrectResponse, ErrorResponse, respond_correct, respond_error
from app.schema.schemas import Citation, QueryRequest, QueryResponse
from app.services.context import build_llm_context_blocks, filter_context_hits, partition_retrieval_hits
from app.services.evidence import confidence_label, filter_primary_hits, is_insufficient
from app.services.llm import generate_answer
from app.services.retriever import hybrid_search

router = APIRouter()


def _normalize_chunk_metadata(raw: object) -> dict[str, str]:
    """Coerce JSONB metadata from Postgres into citation-safe string values."""
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


@router.post(
    "",
    response_model=CorrectResponse[QueryResponse],
    responses={
        200: {"model": CorrectResponse[QueryResponse], "description": "Answer or controlled refusal"},
        502: {"model": ErrorResponse, "description": "Retrieval or generation failure"},
    },
)
async def query(body: QueryRequest, response: Response) -> CorrectResponse[QueryResponse] | ErrorResponse:
    """Retrieve tenant-scoped chunks; answer or refuse based on evidence scores."""
    try:
        hits = await hybrid_search(body.tenant_id, body.question, role=body.role)
    except Exception as exc:
        return respond_error(
            response,
            error_code="retrieval_failed",
            detail=str(exc),
            status_code=502,
            message="hybrid_search_failed",
        )

    primary_hits, context_hits = partition_retrieval_hits(hits)
    all_primary_scores = [float(hit["score"]) for hit in primary_hits]

    if is_insufficient(all_primary_scores):
        payload = QueryResponse(
            answer="Not enough indexed evidence to answer this question.",
            citations=[],
            confidence="low",
            insufficient_evidence=True,
        )
        return respond_correct(
            response,
            payload,
            status_code=200,
            message="insufficient_evidence",
        )

    kept_primaries = filter_primary_hits(primary_hits)
    if not kept_primaries:
        payload = QueryResponse(
            answer="Not enough indexed evidence to answer this question.",
            citations=[],
            confidence="low",
            insufficient_evidence=True,
        )
        return respond_correct(
            response,
            payload,
            status_code=200,
            message="insufficient_evidence",
        )

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
        answer = await generate_answer(body.question, context_blocks)
    except Exception as exc:
        return respond_error(
            response,
            error_code="generation_failed",
            detail=str(exc),
            status_code=502,
            message="llm_generation_failed",
        )

    if answer.strip().upper().startswith("INSUFFICIENT_EVIDENCE"):
        payload = QueryResponse(
            answer="Retrieved sources do not contain a complete answer.",
            citations=[],
            confidence="low",
            insufficient_evidence=True,
        )
        return respond_correct(
            response,
            payload,
            status_code=200,
            message="insufficient_evidence",
        )

    payload = QueryResponse(
        answer=answer,
        citations=citations,
        confidence=confidence,
        insufficient_evidence=False,
    )
    return respond_correct(
        response,
        payload,
        status_code=200,
        message="query_answered",
    )
