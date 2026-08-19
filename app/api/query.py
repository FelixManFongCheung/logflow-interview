"""Grounded query API route."""

from fastapi import APIRouter, Response

from app.schema.responses import CorrectResponse, ErrorResponse, respond_correct, respond_error
from app.schema.schemas import Citation, QueryRequest, QueryResponse
from app.services.evidence import confidence_label, is_insufficient
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
    """Retrieve tenant-scoped chunks and answer only when evidence is strong enough."""
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

    scores = [float(hit["score"]) for hit in hits]
    citations = [
        Citation(
            document_id=hit["document_id"],
            chunk_id=hit["chunk_id"],
            score=round(float(hit["score"]), 4),
            title=hit.get("title"),
            header_path=hit.get("header_path"),
            metadata=_normalize_chunk_metadata(hit.get("metadata")),
        )
        for hit in hits
    ]
    confidence = confidence_label(scores)

    if is_insufficient(scores):
        payload = QueryResponse(
            answer=(
                "I do not have enough evidence in the indexed knowledge base for this tenant to answer that question."
            ),
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

    context_blocks = [f"[{hit['document_id']} / {hit['chunk_id']}]\n{hit['content']}" for hit in hits]
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
            answer=(
                "The retrieved documents are related but do not contain a complete answer. "
                "I will not guess missing operational details."
            ),
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
