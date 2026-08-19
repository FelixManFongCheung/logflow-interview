from fastapi import APIRouter, Response

from app.schema.responses import CorrectResponse, ErrorResponse, HealthData, respond_correct, respond_error
from app.schema.schemas import IngestRequest, IngestResponse
from app.services.retriever import ingest_documents

router = APIRouter()


@router.post(
    "",
    response_model=CorrectResponse[IngestResponse],
    responses={
        201: {"model": CorrectResponse[IngestResponse], "description": "Documents indexed"},
        502: {"model": ErrorResponse, "description": "Embedding or database failure"},
    },
)
async def ingest(body: IngestRequest, response: Response) -> CorrectResponse[IngestResponse] | ErrorResponse:
    """Chunk, embed, and upsert documents for a tenant."""
    try:
        result = await ingest_documents(
            body.tenant_id,
            [document.model_dump() for document in body.documents],
        )
    except Exception as exc:
        return respond_error(
            response,
            error_code="ingest_failed",
            detail=str(exc),
            status_code=502,
            message="document_ingest_failed",
        )

    payload = IngestResponse(tenant_id=body.tenant_id, **result)
    return respond_correct(
        response,
        payload,
        status_code=201,
        message="documents_ingested",
    )
