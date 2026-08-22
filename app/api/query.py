"""Query route."""

from fastapi import APIRouter, Response
from langsmith import traceable

from app.schema.responses import CorrectResponse, ErrorResponse, respond_correct, respond_error
from app.schema.schemas import QueryRequest, QueryResponse
from app.services.query_pipeline import GenerationFailed, RetrievalFailed, run_rag_query

router = APIRouter()


@router.post(
    "",
    response_model=CorrectResponse[QueryResponse],
    responses={
        200: {"model": CorrectResponse[QueryResponse], "description": "Answer or controlled refusal"},
        502: {"model": ErrorResponse, "description": "Retrieval or generation failure"},
    },
)
@traceable(name="query", run_type="chain")
async def query(body: QueryRequest, response: Response) -> CorrectResponse[QueryResponse] | ErrorResponse:
    """Retrieve tenant-scoped chunks; answer or refuse based on evidence scores."""
    try:
        payload = await run_rag_query(body.tenant_id, body.question, role=body.role)
    except RetrievalFailed as exc:
        return respond_error(
            response,
            error_code="retrieval_failed",
            detail=str(exc),
            status_code=502,
            message="hybrid_search_failed",
        )
    except GenerationFailed as exc:
        return respond_error(
            response,
            error_code="generation_failed",
            detail=str(exc),
            status_code=502,
            message="llm_generation_failed",
        )

    message = "insufficient_evidence" if payload.insufficient_evidence else "query_answered"
    return respond_correct(response, payload, status_code=200, message=message)
